from typing import Callable

import rlutils.infra as rl_infra
import rlutils.np as rln
import rlutils.pytorch as rlu
import rlutils.pytorch.utils as ptu
from rlutils.pytorch.algos.mf.dqn import DQN


class AtariDQN(DQN):
    def __init__(self,
                 obs_spec,
                 act_spec,
                 frame_stack=4,
                 double_q=True,
                 q_lr=1e-4,
                 gamma=0.99,
                 tau=5e-3,
                 epsilon_greedy_steps=1000000,
                 huber_delta=None
                 ):
        assert obs_spec.shape == (84, 84), 'The environment must be Atari Games with 84x84 input'
        self.frame_stack = frame_stack
        super(AtariDQN, self).__init__(obs_spec=obs_spec, act_spec=act_spec, double_q=double_q,
                                       q_lr=q_lr, gamma=gamma, tau=tau, huber_delta=huber_delta,
                                       epsilon_greedy_steps=epsilon_greedy_steps)

    def _create_q_network(self):
        return rlu.nn.values.AtariDuelQModule(frame_stack=self.frame_stack, action_dim=self.act_dim).to(ptu.device)

    def _create_epsilon_greedy_scheduler(self):
        return rln.schedulers.LinearSchedule(schedule_timesteps=self.epsilon_greedy_steps,
                                             final_p=0.1,
                                             initial_p=1.0)


class Runner(rl_infra.runner.PytorchAtariRunner):
    @classmethod
    def main(cls,
             env_name,
             env_fn: Callable = None,
             exp_name: str = None,
             steps_per_epoch=10000,
             epochs=150,
             start_steps=10000,
             update_after=5000,
             update_every=4,
             update_per_step=0.25,
             policy_delay=1,
             batch_size=32,
             num_parallel_env=1,
             num_test_episodes=10,
             seed=1,
             # agent args
             q_lr=1e-4,
             tau=5e-3,
             gamma=0.99,
             # replay
             replay_size=int(1e6),
             logger_path: str = None
             ):
        agent_kwargs = dict(
            q_lr=q_lr,
            tau=tau,
            gamma=gamma,
        )

        super(Runner, cls).main(env_name=env_name,
                                env_fn=None,
                                exp_name=exp_name,
                                steps_per_epoch=steps_per_epoch,
                                epochs=epochs,
                                start_steps=start_steps,
                                update_after=update_after,
                                update_every=update_every,
                                update_per_step=update_per_step,
                                policy_delay=1,
                                batch_size=batch_size,
                                num_parallel_env=1,
                                num_test_episodes=num_test_episodes,
                                agent_cls=AtariDQN,
                                agent_kwargs=agent_kwargs,
                                seed=seed,
                                logger_path=logger_path
                                )


if __name__ == '__main__':
    ptu.set_device('cuda')
    rl_infra.runner.run_func_as_main(Runner.main)
