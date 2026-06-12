# backtest/rl_compare_algorithms.py

import os
import random
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch

from backtest.rl_env import NpsPortfolioEnv
from backtest.dqn_agent import DQNAgent


@dataclass
class ExperimentResult:
    algorithm: str
    seed: int
    total_reward: float
    avg_reward: float
    final_equity: float
    total_return_pct: float
    win_rate: float
    trades: int


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def choose_epsilon_greedy(
    q_table: np.ndarray,
    state_idx: int,
    action_size: int,
    epsilon: float,
) -> int:
    if random.random() < epsilon:
        return random.randrange(action_size)

    return int(np.argmax(q_table[state_idx]))


def train_q_learning(
    env: NpsPortfolioEnv,
    episodes: int = 50,
    alpha: float = 0.1,
    gamma: float = 0.95,
    epsilon: float = 1.0,
    epsilon_decay: float = 0.995,
    epsilon_min: float = 0.05,
):
    """
    Tabular Q-Learning 비교실험.

    주의:
    NpsPortfolioEnv의 실제 state는 고차원 벡터지만,
    Q-Learning은 테이블 기반이므로 비교실험에서는 state를 날짜 index로 단순화한다.
    """
    state_size = len(env.dates)
    action_size = env.action_size

    q_table = np.zeros((state_size, action_size))
    episode_rewards: list[float] = []

    for _ in range(episodes):
        env.reset()
        state_idx = env.current_idx
        done = False
        total_reward = 0.0

        while not done:
            action = choose_epsilon_greedy(
                q_table=q_table,
                state_idx=state_idx,
                action_size=action_size,
                epsilon=epsilon,
            )

            _, reward, done, _ = env.step(action)
            next_state_idx = env.current_idx

            best_next_q = np.max(q_table[next_state_idx])

            q_table[state_idx, action] += alpha * (
                reward + gamma * best_next_q - q_table[state_idx, action]
            )

            state_idx = next_state_idx
            total_reward += reward

        epsilon = max(epsilon_min, epsilon * epsilon_decay)
        episode_rewards.append(float(total_reward))

    return q_table, episode_rewards


def train_sarsa(
    env: NpsPortfolioEnv,
    episodes: int = 50,
    alpha: float = 0.1,
    gamma: float = 0.95,
    epsilon: float = 1.0,
    epsilon_decay: float = 0.995,
    epsilon_min: float = 0.05,
):
    """
    Tabular SARSA 비교실험.

    주의:
    실제 state는 고차원이지만,
    SARSA도 테이블 기반이므로 state를 날짜 index로 단순화한다.
    """
    state_size = len(env.dates)
    action_size = env.action_size

    q_table = np.zeros((state_size, action_size))
    episode_rewards: list[float] = []

    for _ in range(episodes):
        env.reset()
        state_idx = env.current_idx

        action = choose_epsilon_greedy(
            q_table=q_table,
            state_idx=state_idx,
            action_size=action_size,
            epsilon=epsilon,
        )

        done = False
        total_reward = 0.0

        while not done:
            _, reward, done, _ = env.step(action)
            next_state_idx = env.current_idx

            next_action = choose_epsilon_greedy(
                q_table=q_table,
                state_idx=next_state_idx,
                action_size=action_size,
                epsilon=epsilon,
            )

            q_table[state_idx, action] += alpha * (
                reward
                + gamma * q_table[next_state_idx, next_action]
                - q_table[state_idx, action]
            )

            state_idx = next_state_idx
            action = next_action
            total_reward += reward

        epsilon = max(epsilon_min, epsilon * epsilon_decay)
        episode_rewards.append(float(total_reward))

    return q_table, episode_rewards


def train_dqn(
    env: NpsPortfolioEnv,
    episodes: int = 50,
):
    """
    DQN 비교실험.
    NpsPortfolioEnv의 고차원 state를 그대로 사용한다.
    """
    agent = DQNAgent(
        state_size=env.state_size,
        action_size=env.action_size,
        learning_rate=0.001,
        gamma=0.95,
        epsilon=1.0,
        epsilon_min=0.05,
        epsilon_decay=0.995,
        batch_size=32,
    )

    episode_rewards: list[float] = []

    for _ in range(episodes):
        state = env.reset()
        done = False
        total_reward = 0.0

        while not done:
            action = agent.select_action(state)

            next_state, reward, done, _ = env.step(action)

            agent.remember(
                state=state,
                action=action,
                reward=reward,
                next_state=next_state,
                done=done,
            )

            agent.train_step()

            state = next_state
            total_reward += reward

        episode_rewards.append(float(total_reward))

    return agent, episode_rewards


def evaluate_tabular(
    env: NpsPortfolioEnv,
    q_table: np.ndarray,
):
    env.reset()
    done = False

    rewards: list[float] = []
    wins = 0
    trades = 0

    while not done:
        state_idx = env.current_idx
        action = int(np.argmax(q_table[state_idx]))

        _, reward, done, info = env.step(action)

        rewards.append(float(reward))

        if info.get("bought") is not None:
            trades += 1

        if reward > 0:
            wins += 1

    final_equity = float(env.prev_equity)
    total_reward = float(np.sum(rewards))
    avg_reward = float(np.mean(rewards)) if rewards else 0.0
    total_return_pct = (final_equity / env.initial_capital - 1.0) * 100
    win_rate = wins / len(rewards) * 100 if rewards else 0.0

    return total_reward, avg_reward, final_equity, total_return_pct, win_rate, trades


def evaluate_dqn(
    env: NpsPortfolioEnv,
    agent: DQNAgent,
):
    state = env.reset()
    done = False

    agent.epsilon = 0.0

    rewards: list[float] = []
    wins = 0
    trades = 0

    while not done:
        action = agent.select_action(state)

        next_state, reward, done, info = env.step(action)

        rewards.append(float(reward))

        if info.get("bought") is not None:
            trades += 1

        if reward > 0:
            wins += 1

        state = next_state

    final_equity = float(env.prev_equity)
    total_reward = float(np.sum(rewards))
    avg_reward = float(np.mean(rewards)) if rewards else 0.0
    total_return_pct = (final_equity / env.initial_capital - 1.0) * 100
    win_rate = wins / len(rewards) * 100 if rewards else 0.0

    return total_reward, avg_reward, final_equity, total_return_pct, win_rate, trades


def build_env(data: pd.DataFrame) -> NpsPortfolioEnv:
    return NpsPortfolioEnv(
        data=data,
        top_k=50,
        holding_period=20,
        transaction_cost=0.001,
        max_positions=10,
        initial_capital=10_000_000,
        min_consecutive_days=0,
        min_net_buy_amount=0.0,
        min_buy_intensity_pct=0.0,
    )


def run_experiments(
    data_path: str = "nps_rl_training_data.csv",
    seeds: tuple[int, ...] = (42, 100, 777, 2025, 9999),
    episodes: int = 50,
    output_path: str = "rl_algorithm_comparison.csv",
) -> None:
    if not os.path.exists(data_path):
        raise FileNotFoundError(
            f"{data_path} 파일이 없습니다. 먼저 make_rl_training_data.py를 실행하세요."
        )

    data = pd.read_csv(data_path)

    if "trade_date" not in data.columns:
        raise ValueError("학습 데이터에 trade_date 컬럼이 없습니다.")

    data["trade_date"] = pd.to_datetime(data["trade_date"]).dt.date

    results: list[ExperimentResult] = []

    for seed in seeds:
        print(f"\n===== Seed {seed} =====")
        set_seed(seed)

        # Q-Learning
        env = build_env(data)
        q_table, _ = train_q_learning(
            env=env,
            episodes=episodes,
            alpha=0.1,
            gamma=0.95,
            epsilon=1.0,
            epsilon_decay=0.995,
            epsilon_min=0.05,
        )
        total, avg, final_equity, total_return, win_rate, trades = evaluate_tabular(
            env=build_env(data),
            q_table=q_table,
        )
        results.append(
            ExperimentResult(
                algorithm="Q-Learning",
                seed=seed,
                total_reward=total,
                avg_reward=avg,
                final_equity=final_equity,
                total_return_pct=total_return,
                win_rate=win_rate,
                trades=trades,
            )
        )
        print(
            f"Q-Learning: reward={total:.4f}, "
            f"return={total_return:.2f}%, win={win_rate:.2f}%, trades={trades}"
        )

        # SARSA
        env = build_env(data)
        sarsa_table, _ = train_sarsa(
            env=env,
            episodes=episodes,
            alpha=0.1,
            gamma=0.95,
            epsilon=1.0,
            epsilon_decay=0.995,
            epsilon_min=0.05,
        )
        total, avg, final_equity, total_return, win_rate, trades = evaluate_tabular(
            env=build_env(data),
            q_table=sarsa_table,
        )
        results.append(
            ExperimentResult(
                algorithm="SARSA",
                seed=seed,
                total_reward=total,
                avg_reward=avg,
                final_equity=final_equity,
                total_return_pct=total_return,
                win_rate=win_rate,
                trades=trades,
            )
        )
        print(
            f"SARSA: reward={total:.4f}, "
            f"return={total_return:.2f}%, win={win_rate:.2f}%, trades={trades}"
        )

        # DQN
        env = build_env(data)
        agent, _ = train_dqn(
            env=env,
            episodes=episodes,
        )
        total, avg, final_equity, total_return, win_rate, trades = evaluate_dqn(
            env=build_env(data),
            agent=agent,
        )
        results.append(
            ExperimentResult(
                algorithm="DQN",
                seed=seed,
                total_reward=total,
                avg_reward=avg,
                final_equity=final_equity,
                total_return_pct=total_return,
                win_rate=win_rate,
                trades=trades,
            )
        )
        print(
            f"DQN: reward={total:.4f}, "
            f"return={total_return:.2f}%, win={win_rate:.2f}%, trades={trades}"
        )

    result_df = pd.DataFrame([r.__dict__ for r in results])
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    summary = (
        result_df.groupby("algorithm")
        .agg(
            mean_total_reward=("total_reward", "mean"),
            std_total_reward=("total_reward", "std"),
            mean_total_return_pct=("total_return_pct", "mean"),
            std_total_return_pct=("total_return_pct", "std"),
            mean_win_rate=("win_rate", "mean"),
            mean_trades=("trades", "mean"),
        )
        .reset_index()
    )

    summary["ci95_total_return_pct"] = (
        1.96 * summary["std_total_return_pct"] / np.sqrt(len(seeds))
    )

    summary_path = "rl_algorithm_comparison_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print(f"\n상세 결과 저장 완료: {output_path}")
    print(result_df)

    print(f"\n요약 결과 저장 완료: {summary_path}")
    print(summary)


if __name__ == "__main__":
    run_experiments()