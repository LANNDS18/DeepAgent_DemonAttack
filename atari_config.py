import numpy as np
from DeepAgent.interfaces.ibaseConfig import BaseConfig

"""
Crop the Original Image Size for Atari Games
"""


def pong_crop(x): return x[30:-10, :]


def demon_attack_crop(x): return x[20:-20, :]


def demon_attack_reward(reward):
    reward = np.sign(reward)
    if reward > 0:
        reward = 0.5
    else:
        reward -= 1e-7
    return reward


def pong_reward(reward): return np.sign(reward)


class PongConfig(BaseConfig):
    USE_GPU = False
    RENDER = True

    TARGET_REWARD = 20

    ENV_NAME = 'PongNoFrameskip-v4'
    CROP = pong_crop
    REWARD_PROCESSOR = pong_reward

    LEARNING_RATE = [[5e-4, 2.5e-4, 5e5], [2.5e-4, 1e-4, 1e6]]

    GAMMA = 0.99
    N_STEP = 10
    ONE_STEP_WEIGHT = 0.5
    N_STEP_WEIGHT = 0.5
    EPS_SCHEDULE = [[1, 0.2, 1e5],
                    [0.2, 0.1, 1e6],
                    [0.1, 0.01, 2e6]]

    TARGET_SYNC_FREQ = 10000
    SAVING_MODEL = True
    LOG_HISTORY = True

    MODEL_LOAD_PATH = './models/DQN_PongNoFrameskip-v4'
    VIDEO_DIR = './video/PongDQN'


class DemonAttackConfig(BaseConfig):
    USE_GPU = False

    RENDER = False
    TARGET_REWARD = 8000

    ENV_NAME = 'DemonAttackNoFrameskip-v4'
    CROP = demon_attack_crop
    REWARD_PROCESSOR = demon_attack_reward

    LEARNING_RATE = [[3e-4, 2.5e-4, 5e5], [2.5e-4, 2e-4, 1e6]]

    GAMMA = 0.99
    N_STEP = 10
    ONE_STEP_WEIGHT = 0.5
    N_STEP_WEIGHT = 0.5
    EPS_SCHEDULE = [[1, 0.1, 1e6],
                    [0.1, 0.01, 2e6],
                    [0.01, 0.001, 5e6]]

    TARGET_SYNC_FREQ = 10000
    SAVING_MODEL = True
    LOG_HISTORY = True

    MODEL_LOAD_PATH = 'models/DDDQN_v1_DemonAttackNoFrameskip-v4'
    VIDEO_DIR = './video/DemonAttackDQN'
