import gym
import numpy as np

from gym import spaces
from collections import deque
from DeepAgent.utils.common import process_frame, LazyFrames


class FireReset(gym.Wrapper):
    """
    Take action on reset for environments that are fixed until firing.
    :param env: the environment to wrap
    """

    def __init__(self, env: gym.Env):
        gym.Wrapper.__init__(self, env)

    def reset(self, **kwargs) -> np.ndarray:
        self.env.reset(**kwargs)
        obs, _, done, _ = self.env.step(1)
        if done:
            self.env.reset(**kwargs)
        obs, _, done, _ = self.env.step(2)
        if done:
            self.env.reset(**kwargs)
        return obs

    def step(self, ac):
        return self.env.step(ac)


class EpisodicLife(gym.Wrapper):
    def __init__(self, env_name):
        """Make end-of-life == end-of-episode, but only reset on true test_env over.
        Done by DeepMind for the DQN and co. since it helps value estimation.
        """
        gym.Wrapper.__init__(self, env_name)
        self.lives = 0
        self.was_real_done = True
        self.episode_returns = 0.0

    def step(self, action):
        obs, reward, done, info = self.env.step(action)
        self.was_real_done = done
        lives = self.env.unwrapped.ale.lives()
        if self.lives > lives > 0:
            done = True
        self.lives = lives
        self.episode_returns += reward
        return obs, reward, done, info

    def reset(self, **kwargs):
        """Reset only when lives are exhausted.
        This way all states are still reachable even though lives are episodic,
        and the learner need not know about any of this behind-the-scenes.
        """
        if self.was_real_done:
            self.episode_returns = 0.0
            obs = self.env.reset(**kwargs)
        else:
            obs, _, _, _ = self.env.step(0)
        self.lives = self.env.unwrapped.ale.lives()
        return obs


class NoopStart(gym.Wrapper):
    def __init__(self, env, noop_max=10):
        """Sample initial states by taking random number of no-ops on reset.
        No-op is assumed to be action 0.
        """
        gym.Wrapper.__init__(self, env)
        self.noop_max = noop_max
        self.override_num_noops = None
        self.noop_action = 0
        assert env.unwrapped.get_action_meanings()[0] == 'NOOP'

    def reset(self, **kwargs):
        """ Do no-op action for a number of steps in [1, noop_max]."""
        self.env.reset(**kwargs)
        if self.override_num_noops is not None:
            noops = self.override_num_noops
        else:
            noops = np.random.randint(1, self.noop_max + 1)
        assert noops > 0
        obs = None
        for _ in range(noops):
            obs, _, done, _ = self.env.step(self.noop_action)
            if done:
                obs = self.env.reset(**kwargs)
        return obs

    def step(self, ac):
        return self.env.step(ac)


class MaxAndSkip(gym.Wrapper):
    def __init__(self, env, skip=4):
        """Return only every `skip`-th frame"""
        gym.Wrapper.__init__(self, env)
        # most recent raw observations (for max pooling across time steps)
        self._obs_buffer = np.zeros((2,) + env.observation_space.shape, dtype=np.uint8)
        self._skip = skip

    def step(self, action):
        """Repeat action, sum reward, and max over last observations."""
        total_reward = 0.0
        done = None
        info = None
        for i in range(self._skip):
            obs, reward, done, info = self.env.step(action)
            if i == self._skip - 2:
                self._obs_buffer[0] = obs
            if i == self._skip - 1:
                self._obs_buffer[1] = obs
            total_reward += reward
            if done:
                break
        max_frame = np.amax(self._obs_buffer, axis=0)
        return max_frame, total_reward, done, info

    def reset(self, **kwargs):
        return self.env.reset(**kwargs)


class StackFrame(gym.Wrapper):
    """Wrapper for the environment provided by Gym"""

    def __init__(self, env, frame_stack=4):
        super().__init__(env)
        self.frame_stack = frame_stack
        self.frames = deque([], maxlen=frame_stack)
        shape = self.env.observation_space.shape
        self.observation_space = spaces.Box(low=0, high=255, shape=(shape[:-1] + (shape[-1] * frame_stack,)),
                                            dtype=env.observation_space.dtype)

    def reset(self):
        ob = self.env.reset()
        for _ in range(self.frame_stack):
            self.frames.append(ob)
        return self._get_ob()

    def step(self, action):
        ob, reward, done, info = self.env.step(action)
        self.frames.append(ob)
        return self._get_ob(), reward, done, info

    def _get_ob(self):
        assert len(self.frames) == self.frame_stack
        return LazyFrames(list(self.frames))


class ProcessFrame(gym.ObservationWrapper):
    def __init__(self, env, output_shape=(84, 84), crop=None):
        """
        Warp frames to 84x84 as done in the Nature paper and later work.
        If the environment uses dictionary observations, `dict_space_key` can be specified which indicates which
        observation should be warped.
        """
        super().__init__(env)
        new_space = gym.spaces.Box(
            low=0,
            high=255,
            shape=(output_shape[0], output_shape[1], 1),
            dtype=np.uint8,
        )
        self.crop = crop
        self.output_shape = output_shape
        self.observation_space = new_space

    def observation(self, obs):
        frame = process_frame(obs, shape=self.output_shape, crop=self.crop)
        return frame


class StepLimit(gym.Wrapper):
    """
        Limit the length of episode be limited
    """

    def __init__(self, env, limit=10000):
        self.limit = limit
        self.step_count = 0
        super().__init__(env)

    def reset(self, **kwargs):
        self.step_count = 0
        return self.env.reset(**kwargs)

    def step(self, action):
        observation, reward, done, info = self.env.step(action)
        self.step_count += 1
        if self.step_count >= self.limit:
            done = True
        return observation, reward, done, info


def mergeWrapper(env_name, frame_stack=4, output_shape=(84, 84), crop=None, train=True):
    env = gym.make(env_name)
    assert 'NoFrameskip' in env.spec.id
    env = NoopStart(env, noop_max=10)
    env = MaxAndSkip(env, skip=4)
    if train:
        env = EpisodicLife(env)
    if "FIRE" in env.unwrapped.get_action_meanings():
        env = FireReset(env)
    env = ProcessFrame(env, output_shape=output_shape, crop=crop)
    env = StepLimit(env)
    if frame_stack:
        env = StackFrame(env, frame_stack=frame_stack)
    return env


class GameEnv(gym.Wrapper):
    """Wrapper for the environment provided by Gym"""

    def __init__(self,
                 env_name,
                 output_shape=(84, 84),
                 frame_stack=4,
                 crop=lambda x: x,
                 reward_processor=lambda x, y, z: x,
                 train=True
                 ):
        env = mergeWrapper(env_name, frame_stack=frame_stack, output_shape=output_shape, train=train, crop=crop)
        self.reward_processor = reward_processor
        self.id = env_name
        self.env = env
        super().__init__(env)

    def reset(self):
        frame = np.array(self.env.reset())
        return frame

    def step(self, action):
        """Performs an action and observes the result
        Arguments:
            action: An integer describe action the agent chose
        Returns:
            next_state: The processed new frame as a result of that action
            reward: The reward for taking that action
            done: Whether the test_env has ended
            info: other information
        """
        next_state, reward, done, info = self.env.step(action)
        reward = self.reward_processor(reward, done, action)
        next_state = np.array(next_state)
        return next_state, reward, done, info
