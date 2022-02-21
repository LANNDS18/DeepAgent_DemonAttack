import tensorflow as tf
import numpy as np

from collections import deque
from DeepAgent.interfaces.IBaseBuffer import IBaseBuffer, Transition


class ExperienceReplay(IBaseBuffer):
    """
    This class manages buffer of agent.
    """

    def __init__(self, size, **kwargs):
        super(ExperienceReplay, self).__init__(size, **kwargs)
        self._buffer = deque(maxlen=size)

    def append(self, *args):
        transition = Transition(*args)
        self._buffer.append(transition)
        self.current_size = len(self._buffer)

    def get_sample_indices(self):
        indices = []
        while len(indices) < self.batch_size:
            index = np.random.randint(low=0, high=self.size, dtype=np.int32)
            indices.append(index)
        return indices

    def get_sample(self, indices):
        states, actions, rewards, dones, new_states = [], [], [], [], []

        for index in indices:
            item = self._buffer[index]
            states.append(tf.constant(item.state, tf.float32))
            actions.append(tf.constant(item.action, tf.int32))
            rewards.append(tf.constant(item.reward, tf.float32))
            dones.append(tf.constant(item.done, tf.bool))
            new_states.append(tf.constant(item.new_state, tf.float32))

        return tf.stack(states, axis=0), tf.stack(actions, axis=0), tf.stack(rewards, axis=0), tf.stack(dones,
                                                                                                        axis=0), tf.stack(
            new_states, axis=0)

    def __len__(self):
        return len(self._buffer)

    def __getitem__(self, i):
        return self._buffer[i]

    def __repr__(self):
        return self.__class__.__name__ + "({})".format(self.size)


class PrioritizedExperienceReplay(ExperienceReplay):
    """
    This Prioritized Experience Replay Memory class
    """

    def __init__(self, size, prob_alpha=0.6, epsilon=1e-3, **kwargs):
        """
        Initialize replay buffer.
        Args:
            size: Buffer maximum size.
            **kwargs: kwargs passed to BaseBuffer.
            prob_alpha: The probability of being assigned the priority
            epsilon: The small priority for new transition appending into buffer
        """
        super(PrioritizedExperienceReplay, self).__init__(size, **kwargs)
        self.size = int(size)
        self._buffer = []
        self.priorities = np.array([])
        self.prob_alpha = prob_alpha
        self.epsilon = epsilon

    def append(self, *args):
        """
        Append experience and auto-allocate to temp buffer / main buffer(self)
        Args:
            *args: Items to store
        """
        transition = Transition(*args)
        if self.current_size < self.size:
            self._buffer.append(transition)
            self.priorities = np.append(
                self.priorities,
                self.epsilon if self.priorities.size == 0 else self.priorities.max())
        else:
            idx = np.argmin(self.priorities)
            self._buffer[idx] = transition
            self.priorities[idx] = self.priorities.max()
        self.current_size = len(self._buffer)

    def get_sample_indices(self):
        probs = self.priorities ** self.prob_alpha
        probs /= probs.sum()
        indices = np.random.choice(len(self._buffer),
                                   self.batch_size,
                                   p=probs,
                                   replace=False)
        return indices

    def update_priorities(self, indices, abs_errors):
        """
        Update priorities for chosen samples
        Args:
            abs_errors: abs of Y and Y_Predict
            indices: The index of the element
        """
        self.priorities[indices] = abs_errors + self.epsilon

    def __len__(self):
        return len(self._buffer)

    def __getitem__(self, i):
        return self._buffer[i]

    def __repr__(self):
        return self.__class__.__name__ + "({})".format(self.size)
