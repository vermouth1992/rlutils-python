import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp
from rlutils.tf.distributions import make_independent_normal_from_params, make_independent_beta_from_params, \
    apply_squash_log_prob
from rlutils.tf.functional import clip_atanh, expand_ensemble_dim
from rlutils.tf.nn.functional import build_mlp

from .base import ConditionalBetaVAE

tfd = tfp.distributions
tfl = tfp.layers

MIN_LOG_SCALE = -10.
MAX_LOG_SCALE = 5.

EPS = 1e-3


class BehaviorPolicy(ConditionalBetaVAE):
    def __init__(self, out_dist, obs_dim, act_dim, mlp_hidden=256):
        self.out_dist = out_dist
        self.obs_dim = obs_dim
        self.act_dim = act_dim
        self.mlp_hidden = mlp_hidden
        super(BehaviorPolicy, self).__init__(latent_dim=self.act_dim * 2, beta=1.0)

    def call(self, inputs, training=None, mask=None):
        x, cond = inputs
        print(f'Tracing _forward with x={x}, cond={cond}')
        posterior = self.encoder(inputs=(x, cond), training=training)
        encode_sample = posterior.sample()
        out = self.decoder((encode_sample, cond), training=training)
        log_likelihood = out.log_prob(x)  # (None,)
        log_likelihood = self.transform_raw_log_prob(log_likelihood, x)
        kl_divergence = tfd.kl_divergence(posterior, self.prior)
        nll = -tf.reduce_mean(log_likelihood, axis=0)
        kld = tf.reduce_mean(kl_divergence, axis=0)
        return nll, kld

    def transform_raw_action(self, action):
        if self.out_dist == 'normal':
            return tf.tanh(action)
        elif self.out_dist == 'beta':
            return (action - 0.5) * 2
        else:
            raise NotImplementedError

    def inverse_transform_action(self, action):
        if self.out_dist == 'normal':
            return clip_atanh(action)
        elif self.out_dist == 'beta':
            raw_action = (action + 1) / 2
            raw_action = tf.clip_by_value(raw_action, EPS, 1. - EPS)
            return raw_action
        else:
            raise NotImplementedError

    def transform_raw_log_prob(self, raw_log_prob, raw_action):
        if self.out_dist == 'beta':
            return raw_log_prob - np.log(2.)
        elif self.out_dist == 'normal':
            return apply_squash_log_prob(raw_log_prob=raw_log_prob, x=raw_action)
        else:
            raise NotImplementedError

    def _make_encoder(self) -> tf.keras.Model:
        obs_input = tf.keras.Input(shape=(self.obs_dim,), dtype=tf.float32)
        act_input = tf.keras.Input(shape=(self.act_dim,), dtype=tf.float32)
        input = tf.concat((act_input, obs_input), axis=-1)
        encoder = build_mlp(input_dim=self.obs_dim + self.act_dim,
                            output_dim=self.latent_dim * 2,
                            mlp_hidden=self.mlp_hidden,
                            num_layers=3)
        encoder.add(tfl.DistributionLambda(
            make_distribution_fn=lambda t: make_independent_normal_from_params(t, min_log_scale=MIN_LOG_SCALE,
                                                                               max_log_scale=MAX_LOG_SCALE)))
        output = encoder(input)
        model = tf.keras.Model(inputs=[act_input, obs_input], outputs=output)
        return model

    def _make_decoder(self) -> tf.keras.Model:
        obs_input = tf.keras.Input(shape=(self.obs_dim,), dtype=tf.float32)
        latent_input = tf.keras.Input(shape=(self.latent_dim,), dtype=tf.float32)
        input = tf.concat((latent_input, obs_input), axis=-1)
        decoder = build_mlp(input_dim=self.obs_dim + self.latent_dim,
                            output_dim=self.act_dim * 2,
                            mlp_hidden=self.mlp_hidden,
                            num_layers=3)
        if self.out_dist == 'beta':
            out_layer = tfl.DistributionLambda(
                make_distribution_fn=lambda t: make_independent_beta_from_params(t))
        elif self.out_dist == 'normal':
            out_layer = tfl.DistributionLambda(
                make_distribution_fn=lambda t: make_independent_normal_from_params(t, min_log_scale=MIN_LOG_SCALE,
                                                                                   max_log_scale=MAX_LOG_SCALE))
        else:
            raise NotImplementedError

        decoder.add(out_layer)
        output = decoder(input)
        model = tf.keras.Model(inputs=[latent_input, obs_input], outputs=output)
        return model

    @tf.function
    def act_batch(self, obs, deterministic=tf.convert_to_tensor(True)):
        print(f'Tracing vae act_batch with obs {obs}')
        pi_final = self.sample(cond=obs, full_path=tf.logical_not(deterministic))
        pi_final = tf.tanh(pi_final)
        return pi_final


class EnsembleBehaviorPolicy(BehaviorPolicy):
    def __init__(self, num_ensembles, out_dist, obs_dim, act_dim, mlp_hidden=256):
        self.num_ensembles = num_ensembles
        super(EnsembleBehaviorPolicy, self).__init__(out_dist=out_dist, obs_dim=obs_dim,
                                                     act_dim=act_dim, mlp_hidden=mlp_hidden)
        self.build(input_shape=[(self.num_ensembles, None, act_dim),
                                (self.num_ensembles, None, obs_dim)])

    def expand_ensemble_dim(self, x):
        """ functionality for outer class to expand before passing into the ensemble model. """
        return expand_ensemble_dim(x, self.num_ensembles)

    def select_random_ensemble(self, x):
        """ x: (num_ensembles, None) """
        batch_size = tf.shape(x)[1]
        indices = tf.stack([tf.random.uniform(shape=[batch_size], maxval=self.num_ensembles, dtype=tf.int32),
                            tf.range(batch_size)], axis=-1)
        x = tf.gather_nd(x, indices=indices)
        return x

    def _make_encoder(self) -> tf.keras.Model:
        obs_input = tf.keras.Input(batch_input_shape=(self.num_ensembles, None, self.obs_dim,), dtype=tf.float32)
        act_input = tf.keras.Input(batch_input_shape=(self.num_ensembles, None, self.act_dim,), dtype=tf.float32)
        input = tf.concat((act_input, obs_input), axis=-1)
        encoder = build_mlp(input_dim=self.obs_dim + self.act_dim,
                            output_dim=self.latent_dim * 2,
                            mlp_hidden=self.mlp_hidden,
                            num_layers=3,
                            num_ensembles=self.num_ensembles)
        encoder.add(tfl.DistributionLambda(
            make_distribution_fn=lambda t: make_independent_normal_from_params(t, min_log_scale=MIN_LOG_SCALE,
                                                                               max_log_scale=MAX_LOG_SCALE)))
        output = encoder(input)
        model = tf.keras.Model(inputs=[act_input, obs_input], outputs=output)
        return model

    def _make_decoder(self) -> tf.keras.Model:
        obs_input = tf.keras.Input(batch_input_shape=(self.num_ensembles, None, self.obs_dim,), dtype=tf.float32)
        latent_input = tf.keras.Input(batch_input_shape=(self.num_ensembles, None, self.latent_dim,),
                                      dtype=tf.float32)
        input = tf.concat((latent_input, obs_input), axis=-1)
        decoder = build_mlp(input_dim=self.obs_dim + self.latent_dim,
                            output_dim=self.act_dim * 2,
                            mlp_hidden=self.mlp_hidden,
                            num_layers=3,
                            num_ensembles=self.num_ensembles)

        if self.out_dist == 'beta':
            out_layer = tfl.DistributionLambda(
                make_distribution_fn=lambda t: make_independent_beta_from_params(t))
        elif self.out_dist == 'normal':
            out_layer = tfl.DistributionLambda(
                make_distribution_fn=lambda t: make_independent_normal_from_params(t, min_log_scale=MIN_LOG_SCALE,
                                                                                   max_log_scale=MAX_LOG_SCALE))
        else:
            raise NotImplementedError

        decoder.add(out_layer)
        output = decoder(input)
        model = tf.keras.Model(inputs=[latent_input, obs_input], outputs=output)
        return model

    @tf.function
    def act_batch(self, obs, deterministic=tf.convert_to_tensor(True)):
        print(f'Tracing vae act_batch with obs {obs}')

        obs = self.expand_ensemble_dim(obs)
        pi_final = self.sample(cond=obs, full_path=tf.logical_not(deterministic))
        # random select one ensemble
        pi_final = self.select_random_ensemble(pi_final)
        pi_final = tf.tanh(pi_final)
        return pi_final

    def call(self, inputs, training=None, mask=None):
        x, cond = inputs
        print(f'Tracing call with x={x}, cond={cond}')
        posterior = self.encoder(inputs=(x, cond), training=training)
        encode_sample = posterior.sample()
        out = self.decoder((encode_sample, cond), training=training)
        log_likelihood = out.log_prob(x)  # (num_ensembles, None)
        log_likelihood = self.transform_raw_log_prob(log_likelihood, x)
        kl_divergence = tfd.kl_divergence(posterior, self.prior)
        nll = -tf.reduce_mean(tf.reduce_sum(log_likelihood, axis=0), axis=0)
        kld = tf.reduce_mean(tf.reduce_sum(kl_divergence, axis=0), axis=0)
        return nll, kld

    def train_step(self, data):
        data = tf.nest.map_structure(lambda x: self.expand_ensemble_dim(x), data)
        result = super(EnsembleBehaviorPolicy, self).train_step(data=data)
        result = tf.nest.map_structure(lambda x: x / self.num_ensembles, result)
        return result

    def test_step(self, data):
        data = tf.nest.map_structure(lambda x: self.expand_ensemble_dim(x), data)
        result = super(EnsembleBehaviorPolicy, self).test_step(data=data)
        result = tf.nest.map_structure(lambda x: x / self.num_ensembles, result)
        return result

    def sample(self, cond, full_path=True):
        print(f'Tracing sample with cond={cond}')
        z = self.prior.sample(sample_shape=tf.shape(cond)[0:2])  # (num_ensembles, None, z_dim)
        z = tf.clip_by_value(z, clip_value_min=-0.5, clip_value_max=0.5)
        out_dist = self.decode_distribution(z=(z, cond))
        return tf.cond(full_path, true_fn=lambda: out_dist.sample(), false_fn=lambda: out_dist.mean())