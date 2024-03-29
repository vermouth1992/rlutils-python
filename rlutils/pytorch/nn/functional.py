import torch
import torch.nn as nn

from .layers import EnsembleDense, SqueezeLayer, LambdaLayer, EnsembleBatchNorm1d

str_to_activation = {
    'relu': nn.ReLU,
    'leaky_relu': nn.LeakyReLU,
    'tanh': nn.Tanh,
    'sigmoid': nn.Sigmoid,
    'softplus': nn.Softplus,
}


def decode_activation(activation):
    if isinstance(activation, str):
        act_fn = str_to_activation.get(activation)
    elif isinstance(activation, nn.Module):
        act_fn = lambda: activation
    elif callable(activation):
        act_fn = lambda: LambdaLayer(activation)
    elif activation is None:
        act_fn = nn.Identity
    else:
        raise ValueError('activation must be a string or callable.')
    return act_fn


def build_mlp(input_dim, output_dim, mlp_hidden, num_ensembles=None, num_layers=3,
              activation='relu', out_activation=None, squeeze=False, dropout=None,
              batch_norm=False, layer_norm=False):
    assert not (batch_norm and layer_norm), "batch_norm and layer_norm can't be True simultaneously"
    if squeeze:
        assert output_dim == 1, "if squeeze, output_dim must have size 1"
    if isinstance(mlp_hidden, int):
        mlp_hidden = [mlp_hidden] * (num_layers - 1)
    elif isinstance(mlp_hidden, list) or isinstance(mlp_hidden, tuple):
        assert len(mlp_hidden) == num_layers - 1, 'len(mlp_hidden) must equal to num_layers - 1.'
    else:
        raise ValueError(f'Unknown type mlp_hidden. Got {type(mlp_hidden)}')

    activation_fn = decode_activation(activation)
    output_activation_fn = decode_activation(out_activation)
    layers = []
    if num_layers == 1:
        if num_ensembles is not None:
            layers.append(EnsembleDense(num_ensembles, input_dim, output_dim))
        else:
            layers.append(nn.Linear(input_dim, output_dim))
    else:
        # first layer
        if num_ensembles is not None:
            layers.append(EnsembleDense(num_ensembles, input_dim, mlp_hidden[0]))
            if batch_norm:
                layers.append(EnsembleBatchNorm1d(num_ensembles=num_ensembles, num_features=mlp_hidden[0]))
        else:
            layers.append(nn.Linear(input_dim, mlp_hidden[0]))
            if batch_norm:
                layers.append(nn.BatchNorm1d(num_features=mlp_hidden[0]))
        layers.append(activation_fn())
        if dropout is not None:
            layers.append(nn.Dropout(p=dropout))

        # intermediate layers
        for i in range(num_layers - 2):
            if num_ensembles is not None:
                layers.append(EnsembleDense(num_ensembles, mlp_hidden[i], mlp_hidden[i + 1]))
                if batch_norm:
                    layers.append(EnsembleBatchNorm1d(num_ensembles=num_ensembles, num_features=mlp_hidden[i + 1]))
            else:
                layers.append(nn.Linear(mlp_hidden[i], mlp_hidden[i + 1]))
                if batch_norm:
                    layers.append(nn.BatchNorm1d(num_features=mlp_hidden[i + 1]))
            layers.append(activation_fn())
            if dropout is not None:
                layers.append(nn.Dropout(p=dropout))

        # final dense layer
        if num_ensembles is not None:
            layers.append(EnsembleDense(num_ensembles, mlp_hidden[-1], output_dim))
        else:
            layers.append(nn.Linear(mlp_hidden[-1], output_dim))

    if out_activation is not None:
        layers.append(output_activation_fn())
    if output_dim == 1 and squeeze is True:
        layers.append(SqueezeLayer(dim=-1))
    model = nn.Sequential(*layers)
    return model


def conv2d_bn_activation_block(in_channels, out_channels, kernel_size, stride, padding, bias=True,
                               normalize=True, activation=nn.ReLU):
    """ conv2d + batchnorm (optional) + relu """
    conv = nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding, bias=bias)
    layers = [conv]
    if normalize:
        layers.append(nn.BatchNorm2d(out_channels))
    if activation is not None:
        layers.append(activation(inplace=True))
    return layers


def get_trainable_params(module: nn.Module):
    trainable_params = filter(lambda p: p.requires_grad, module.parameters())
    return trainable_params


def freeze(module: nn.Module):
    for param in module.parameters():
        param.requires_grad = False


def unfreeze(module: nn.Module):
    for param in module.parameters():
        param.requires_grad = True


def get_state_dict(module: nn.Module):
    state_dict = module.state_dict()
    for k, v in state_dict.items():
        state_dict[k] = v.cpu()
    return state_dict


def unsqueeze_and_repeat(tensor: torch.Tensor, dim: int, repeat: int):
    """unsqueeze a tensor and

    Args:
        tensor: a Pytorch Tensor
        dim:
        repeat:

    Returns:

    """
    tensor = torch.unsqueeze(tensor, dim=dim)
    repeats = [1 for _ in range(len(tensor.shape))]
    repeats[dim] = repeat
    tensor = tensor.repeat(*repeats)
    return tensor
