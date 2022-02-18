from collections import deque
from datetime import datetime

import numpy as np
import tensorflow as tf
from tensorflow.keras.optimizers import Adam

from DeepRL.networks.cnn import DQNNetwork
from DeepRL.utils.buffer import ExperienceReplay
from DeepRL.utils.game import GameEnv


class Agent:
    """
    Class for DQN model architecture.
    """

    def __init__(self, env="DemonAttackNoFrameskip-v4"):
        self.game_id = env
        self.env = GameEnv(self.game_id)
        self.gamma = 0.99
        self.batch_size = 32
        self.update_frequency = 4
        self.target_network_update_freq = 1000
        self.history_length = 4
        self.memory = ExperienceReplay(size=200, batch_size=self.batch_size)
        self.model = DQNNetwork(n_actions=self.env.action_space.n,
                                frame_stack=self.history_length)
        self.target_network = DQNNetwork(n_actions=self.env.action_space.n,
                                         frame_stack=self.history_length)
        self.optimizer = Adam(learning_rate=1e-4, epsilon=1e-6)

        self.epsilon_start = 1.0
        self.epsilon_end = 0.02
        self.epsilon_decay_steps = 1000000

        self.replay_start_size = 250
        self.loss = tf.keras.losses.Huber()
        self.loss_metric = tf.keras.metrics.Mean(name="loss")
        self.q_metric = tf.keras.metrics.Mean(name="Q_value")
        self.training_frames = int(1e7)
        self.log_path = "./log/" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + self.game_id
        self.summary_writer = tf.summary.create_file_writer(self.log_path + "/summary/")
        self.life_game = None
        self.print_log_interval = 1
        self.save_weight_interval = 100

        self.env.reset()
        _, _, _, info = self.env.step(0)
        if info["lives"] > 0:
            self.life_game = True
        else:
            self.life_game = False

    @tf.function
    def get_action(self, state, exploration_rate):
        """Get action by ε-greedy method.

        Args:
            state (np.uint8): recent self.history_length frames. (Default: (84, 84, 4))
            exploration_rate (int): Exploration rate for deciding random or optimal action.

        Returns:
            action (tf.int32): Action index
        """
        recent_state = tf.expand_dims(state, axis=0)
        if tf.random.uniform((), minval=0, maxval=1, dtype=tf.float32) < exploration_rate:
            action = tf.random.uniform((), minval=0, maxval=self.env.action_space.n, dtype=tf.int32)
        else:
            q_value = self.model(tf.cast(recent_state, tf.float32))
            action = tf.cast(tf.squeeze(tf.math.argmax(q_value, axis=1)), dtype=tf.int32)
        return action

    @tf.function
    def get_eps(self, current_step, terminal_eps=0.01, terminal_frame_factor=25):
        """Use annealing schedule similar like: https://openai.com/blog/openai-baselines-dqn/ .

        Args:
            current_step (int): Number of entire total_step agent experienced.
            terminal_eps (float): Final exploration rate arrived at terminal_frame_factor * self.epsilon_decay_steps.
            terminal_frame_factor (int): Final exploration frame, which is terminal_frame_factor * self.epsilon_decay_steps.

        Returns:
            eps (float): Calculated epsilon for ε-greedy at current_step.
        """
        terminal_eps_frame = self.epsilon_decay_steps * terminal_frame_factor

        if current_step < self.replay_start_size:
            eps = self.epsilon_start
        elif current_step < self.epsilon_decay_steps:
            eps = (self.epsilon_end - self.epsilon_start) / (self.epsilon_decay_steps - self.replay_start_size) * (
                    current_step - self.replay_start_size) + self.epsilon_start
        elif current_step < terminal_eps_frame:
            eps = (terminal_eps - self.epsilon_end) / (terminal_eps_frame - self.epsilon_decay_steps) * (
                    current_step - self.epsilon_decay_steps) + self.epsilon_end
        else:
            eps = terminal_eps
        return eps

    @tf.function
    def update_main_q_network(self, states, actions, rewards, dones, new_states):
        """Update main q network by experience replay method.

        Args:
            states (tf.float32): Batch of states.
            actions (tf.int32): Batch of actions.
            rewards (tf.float32): Batch of rewards.
            new_states (tf.float32): Batch of next states.
            dones (tf.bool): Batch or terminal status.

        Returns:
            loss (tf.float32): Huber loss of temporal difference.
        """

        with tf.GradientTape() as tape:
            next_state_q = self.target_network(new_states)
            next_state_max_q = tf.math.reduce_max(next_state_q, axis=1)
            expected_q = rewards + self.gamma * next_state_max_q * (
                    1.0 - tf.cast(dones, tf.float32))
            main_q = tf.reduce_sum(
                self.model(states) * tf.one_hot(actions, self.env.action_space.n, 1.0, 0.0),
                axis=1)
            loss = self.loss(tf.stop_gradient(expected_q), main_q)

        gradients = tape.gradient(loss, self.model.trainable_variables)
        clipped_gradients = [tf.clip_by_norm(grad, 10) for grad in gradients]
        self.optimizer.apply_gradients(zip(clipped_gradients, self.model.trainable_variables))
        self.loss_metric.update_state(loss)
        self.q_metric.update_state(main_q)

        return loss

    @tf.function
    def update_target_network(self):
        """Synchronize weights of target network by those of main network."""

        main_vars = self.model.trainable_variables
        target_vars = self.target_network.trainable_variables
        for main_var, target_var in zip(main_vars, target_vars):
            target_var.assign(main_var)

    def train(self):

        total_step = 0
        episode = 0
        latest_100_score = deque(maxlen=100)

        while total_step < self.training_frames:

            state = self.env.reset()
            episode_step = 0
            episode_score = 0.0
            done = False

            while not done:
                self.env.render()

                eps = self.get_eps(tf.constant(total_step, tf.float32))
                action = self.get_action(tf.constant(state), tf.constant(eps, tf.float32))

                next_state, reward, done, info = self.env.step(action)
                episode_score += reward

                self.memory.append(state, action, reward, done, next_state)
                state = next_state

                if (total_step % self.update_frequency == 0) and (total_step > self.replay_start_size):
                    indices = self.memory.get_sample_indices()
                    state_batch, action_batch, reward_batch, terminal_batch, next_state_batch = self.memory.get_sample(
                        indices)
                    self.update_main_q_network(state_batch, action_batch, reward_batch,
                                               terminal_batch, next_state_batch)

                if (total_step % self.target_network_update_freq == 0) and (total_step > self.replay_start_size):
                    self.update_target_network()

                total_step += 1
                episode_step += 1

                if done:
                    latest_100_score.append(episode_score)
                    print(f'episode{episode}')
                    self.write_summary(episode, latest_100_score, episode_score, total_step, eps)
                    episode += 1

                    if episode % self.print_log_interval == 0:
                        print("Episode: ", episode)
                        print("Latest 100 avg: {:.4f}".format(np.mean(latest_100_score)))
                        print("Progress: {} / {} ( {:.2f} % )".format(total_step, self.training_frames,
                                                                      np.round(total_step / self.training_frames,
                                                                               3) * 100))

                    if episode % self.save_weight_interval == 0:
                        print("Saving weights...")
                        self.model.save_weights(self.log_path + "/weights/")
                        # self.play(self.log_path + "/weights/", episode=episode)

    def play(self, load_dir=None, episode=None, trial=5, max_playing_time=10):

        if load_dir:
            loaded_ckpt = tf.train.latest_checkpoint(load_dir)
            self.model.load_weights(loaded_ckpt)

        frame_set = []
        reward_set = []
        test_env = GameEnv(self.game_id)
        for _ in range(trial):

            state = test_env.reset()
            frames = []
            test_step = 0
            test_reward = 0
            done = False
            test_memory = ExperienceReplay(1000000)

            while not done:

                frames.append(test_env.render())

                action = self.get_action(tf.constant(state, tf.float32), tf.constant(0.0, tf.float32))

                next_state, reward, done, info = test_env.step(action)
                test_reward += reward

                test_memory.append(state, action, reward, done, next_state)
                state = next_state

                test_step += 1

                if done and self.life_game and (info["lives"] != 0):
                    test_env.reset()
                    test_step = 0
                    done = False

                if len(frames) > 15 * 60 * max_playing_time:  # To prevent falling infinite repeating sequences.
                    print("Playing takes {} minutes. Force termination.".format(max_playing_time))
                    break

            reward_set.append(test_reward)
            frame_set.append(frames)

        best_score = np.max(reward_set)
        print("Best score of current network ({} trials): {}".format(trial, best_score))

        if episode is not None:
            with self.summary_writer.as_default():
                tf.summary.scalar("Test score", best_score, step=episode)

    def write_summary(self, episode, latest_100_score, episode_score, total_step, eps):

        with self.summary_writer.as_default():
            tf.summary.scalar("Reward (clipped)", episode_score, step=episode)
            tf.summary.scalar("Latest 100 avg reward (clipped)", np.mean(latest_100_score), step=episode)
            tf.summary.scalar("Loss", self.loss_metric.result(), step=episode)
            tf.summary.scalar("Average Q", self.q_metric.result(), step=episode)
            tf.summary.scalar("Total Frames", total_step, step=episode)
            tf.summary.scalar("Epsilon", eps, step=episode)

        self.loss_metric.reset_states()
        self.q_metric.reset_states()
