# backtest/rl_train.py

import pandas as pd
import os
from backtest.rl_env import NpsStockEnv
from backtest.dqn_agent import DQNAgent


def train_dqn(data_path: str):
    data = pd.read_csv(data_path)

    # ⚠️ 이 3개 값은 추론 시 get_today_recommendation 에 넘기는 FollowStrategy
    #    (min_consecutive_days / min_net_buy_amount / min_buy_intensity_pct)와
    #    반드시 동일해야 한다. 모델은 "이 필터로 만든 좌석표"에 종속된다.
    MIN_CONSECUTIVE_DAYS = 0
    MIN_NET_BUY_AMOUNT = 0.0
    MIN_BUY_INTENSITY_PCT = 0.0

    env = NpsStockEnv(
        data=data,
        top_k=50,
        holding_period=20,
        transaction_cost=0.001,
        min_consecutive_days=MIN_CONSECUTIVE_DAYS,
        min_net_buy_amount=MIN_NET_BUY_AMOUNT,
        min_buy_intensity_pct=MIN_BUY_INTENSITY_PCT,
    )

    agent = DQNAgent(
        state_size=env.state_size,
        action_size=env.action_size
    )

    episodes = 50

    for episode in range(episodes):
        state = env.reset()

        total_reward = 0
        done = False
        selected_trades = []

        while not done:
            action = agent.select_action(state)

            next_state, reward, done, info = env.step(action)

            agent.remember(
                state,
                action,
                reward,
                next_state,
                done
            )

            agent.train_step()

            state = next_state
            total_reward += reward
            selected_trades.append(info)

        print(
            f"Episode {episode + 1}/{episodes}, "
            f"Total Reward: {total_reward:.4f}, "
            f"Epsilon: {agent.epsilon:.4f}"
        )

    os.makedirs("models", exist_ok=True)
    agent.save("models/dqn_nps_stock_model.pth")

    return agent


if __name__ == "__main__":
    train_dqn("nps_rl_training_data.csv")