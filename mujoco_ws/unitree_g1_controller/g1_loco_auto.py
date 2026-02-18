#!/usr/bin/env python3
import argparse
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient


def run_option(client: LocoClient, option_id: int) -> None:
    if option_id == 0:
        client.Damp()
    elif option_id == 1:
        client.Damp()
        time.sleep(0.5)
        client.Squat2StandUp()
    elif option_id == 2:
        client.StandUp2Squat()
    elif option_id == 3:
        client.Move(0.3, 0.0, 0.0)
    elif option_id == 4:
        client.Move(0.0, 0.3, 0.0)
    elif option_id == 5:
        client.Move(0.0, 0.0, 0.3)
    elif option_id == 6:
        client.LowStand()
    elif option_id == 7:
        client.HighStand()
    elif option_id == 8:
        client.ZeroTorque()
    elif option_id == 9:
        client.WaveHand()
    elif option_id == 10:
        client.WaveHand(True)
    elif option_id == 11:
        client.ShakeHand()
        time.sleep(3.0)
        client.ShakeHand()
    elif option_id == 12:
        client.Damp()
        time.sleep(0.5)
        client.Lie2StandUp()


def main() -> None:
    parser = argparse.ArgumentParser(description="Non-interactive G1 loco example wrapper")
    parser.add_argument("--interface", type=str, default="lo")
    parser.add_argument("--domain-id", type=int, default=1)
    parser.add_argument("--auto-option", type=int, default=7)
    parser.add_argument("--period", type=float, default=1.0)
    args = parser.parse_args()

    print("WARNING: Please ensure there are no obstacles around the robot while running this example.")
    ChannelFactoryInitialize(args.domain_id, args.interface)

    client = LocoClient()
    client.SetTimeout(10.0)
    client.Init()

    print(f"Auto mode: option id {args.auto_option}, period {args.period}s")
    while True:
        run_option(client, args.auto_option)
        time.sleep(args.period)


if __name__ == "__main__":
    main()
