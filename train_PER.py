from DeepAgent.policy import DuelingPolicy
from DeepAgent.utils import PrioritizedExperienceReplay, GameEnv, TrainWrapper
from DeepAgent.agents import D3NPERAgent

from atari_config import PongConfig

if __name__ == '__main__':
    _config = PongConfig
    agent = TrainWrapper(
        config=_config,
        env=GameEnv,
        buffer=PrioritizedExperienceReplay,
        policy=DuelingPolicy,
        agent=D3NPERAgent,
        train_id='D3N_PER')

    agent.learn(
        max_steps=_config.MAX_STEP,
        target_reward=_config.TARGET_REWARD,
        render=_config.RENDER,
    )
