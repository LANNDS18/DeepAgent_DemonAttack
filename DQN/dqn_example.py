from deep_agent.agents.dqn import DQNAgent
from deep_agent.networks.dqn import build_dqn_network
from deep_agent.utils.buffer import ExperienceReplay
from deep_agent.utils.game import GameEnv


def train_dqn():
    buffer_size = 10000
    game = GameEnv('DemonAttack-v0')
    model = build_dqn_network(game.action_space.n)
    buffer = ExperienceReplay(size=buffer_size)
    agent = DQNAgent(game, model=model, buffer=buffer)
    agent.fill_buffer()
    agent.learn(target_reward=1000)


if __name__ == '__main__':
    train_dqn()
