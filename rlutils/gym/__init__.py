import gym

print(f'Using gym version: {gym.__version__}. We print gym version here as the API is changing frequently.')

from gym import register, make

from . import utils
from . import vector
from . import wrappers

__all__ = ['make']

for var in ['ResetObs']:
    register(
        id=f'Ant{var}-v2',
        entry_point=f'rlutils.gym.envs:Ant{var}Env',
        max_episode_steps=1000,
        reward_threshold=6000.0,
    )

    register(
        id=f'Hopper{var}-v2',
        entry_point=f'rlutils.gym.envs:Hopper{var}Env',
        max_episode_steps=1000,
        reward_threshold=6000.0,
    )

    register(
        id=f'Walker2d{var}-v2',
        entry_point=f'rlutils.gym.envs:Walker2d{var}Env',
        max_episode_steps=1000,
    )

    register(
        id=f'Humanoid{var}-v2',
        entry_point=f'rlutils.gym.envs:Humanoid{var}Env',
        max_episode_steps=1000,
    )

    register(
        id=f'HalfCheetah{var}-v2',
        entry_point=f'rlutils.gym.envs:HalfCheetah{var}Env',
        max_episode_steps=1000,
        reward_threshold=4800.0,
    )

for var in ['TruncatedObs']:
    register(
        id=f'Ant{var}-v2',
        entry_point=f'rlutils.gym.envs:Ant{var}Env',
        max_episode_steps=1000,
        reward_threshold=6000.0,
    )

    register(
        id=f'Humanoid{var}-v2',
        entry_point=f'rlutils.gym.envs:Humanoid{var}Env',
        max_episode_steps=1000,
    )

register(
    id='PendulumResetObs-v0',
    entry_point='rlutils.gym.envs:PendulumResetObsEnv',
    max_episode_steps=200,
)

register(
    id="HopperMB-v4",
    entry_point="rlutils.gym.envs.model_based.mujoco.hopper_v4:HopperEnv",
    max_episode_steps=1000,
    reward_threshold=3800.0,
)

register(
    id="PendulumMB-v1",
    entry_point="rlutils.gym.envs.model_based.classic_control.pendulum:PendulumEnv",
    max_episode_steps=200,
)
