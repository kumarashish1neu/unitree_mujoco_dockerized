import time
import sys
import argparse
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.g1.arm.g1_arm_action_client import G1ArmActionClient
from unitree_sdk2py.g1.arm.g1_arm_action_client import action_map
from dataclasses import dataclass

@dataclass
class TestOption:
    name: str
    id: int

option_list = [
    TestOption(name="release arm", id=0),     
    TestOption(name="shake hand", id=1),    
    TestOption(name="high five", id=2), 
    TestOption(name="hug", id=3), 
    TestOption(name="high wave", id=4),
    TestOption(name="clap", id=5), 
    TestOption(name="face wave", id=6),
    TestOption(name="left kiss", id=7),
    TestOption(name="heart", id=8),
    TestOption(name="right heart", id=9),
    TestOption(name="hands up", id=10),
    TestOption(name="x-ray", id=11),
    TestOption(name="right hand up", id=12),
    TestOption(name="reject", id=13),
    TestOption(name="right kiss", id=14), 
    TestOption(name="two-hand kiss", id=15),  
    
]

class UserInterface:
    def __init__(self):
        self.test_option_ = None

    def convert_to_int(self, input_str):
        try:
            return int(input_str)
        except ValueError:
            return None

    def terminal_handle(self):
        input_str = input("Enter id or name: \n")

        if input_str == "list":
            self.test_option_.name = None
            self.test_option_.id = None
            for option in option_list:
                print(f"{option.name}, id: {option.id}")
            return

        for option in option_list:
            if input_str == option.name or self.convert_to_int(input_str) == option.id:
                self.test_option_.name = option.name
                self.test_option_.id = option.id
                print(f"Test: {self.test_option_.name}, test_id: {self.test_option_.id}")
                return

        print("No matching test option found.")

def run_action(armAction_client: G1ArmActionClient, action_id: int):
    if action_id == 0:
        armAction_client.ExecuteAction(action_map.get("release arm"))
    elif action_id == 1:
        armAction_client.ExecuteAction(action_map.get("shake hand"))
        time.sleep(2)
        armAction_client.ExecuteAction(action_map.get("release arm"))
    elif action_id == 2:
        armAction_client.ExecuteAction(action_map.get("high five"))
        time.sleep(2)
        armAction_client.ExecuteAction(action_map.get("release arm"))
    elif action_id == 3:
        armAction_client.ExecuteAction(action_map.get("hug"))
        time.sleep(2)
        armAction_client.ExecuteAction(action_map.get("release arm"))
    elif action_id == 4:
        armAction_client.ExecuteAction(action_map.get("high wave"))
    elif action_id == 5:
        armAction_client.ExecuteAction(action_map.get("clap"))
    elif action_id == 6:
        armAction_client.ExecuteAction(action_map.get("face wave"))
    elif action_id == 7:
        armAction_client.ExecuteAction(action_map.get("left kiss"))
    elif action_id == 8:
        armAction_client.ExecuteAction(action_map.get("heart"))
        time.sleep(2)
        armAction_client.ExecuteAction(action_map.get("release arm"))
    elif action_id == 9:
        armAction_client.ExecuteAction(action_map.get("right heart"))
        time.sleep(2)
        armAction_client.ExecuteAction(action_map.get("release arm"))
    elif action_id == 10:
        armAction_client.ExecuteAction(action_map.get("hands up"))
        time.sleep(2)
        armAction_client.ExecuteAction(action_map.get("release arm"))
    elif action_id == 11:
        armAction_client.ExecuteAction(action_map.get("x-ray"))
        time.sleep(2)
        armAction_client.ExecuteAction(action_map.get("release arm"))
    elif action_id == 12:
        armAction_client.ExecuteAction(action_map.get("right hand up"))
        time.sleep(2)
        armAction_client.ExecuteAction(action_map.get("release arm"))
    elif action_id == 13:
        armAction_client.ExecuteAction(action_map.get("reject"))
        time.sleep(2)
        armAction_client.ExecuteAction(action_map.get("release arm"))
    elif action_id == 14:
        armAction_client.ExecuteAction(action_map.get("right kiss"))
    elif action_id == 15:
        armAction_client.ExecuteAction(action_map.get("two-hand kiss"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interface", type=str, default="lo")
    parser.add_argument("--domain-id", type=int, default=0)
    parser.add_argument("--auto-action", type=int, default=None, help="Run action id in loop (non-interactive)")
    parser.add_argument("--period", type=float, default=3.0, help="Auto action period in seconds")
    parser.add_argument("--no-confirm", action="store_true", help="Skip Enter prompt")
    args = parser.parse_args()

    print("WARNING: Please ensure there are no obstacles around the robot while running this example.")
    if not args.no_confirm:
        input("Press Enter to continue...")

    ChannelFactoryInitialize(args.domain_id, args.interface)

    test_option = TestOption(name=None, id=None) 
    user_interface = UserInterface()
    user_interface.test_option_ = test_option

    armAction_client = G1ArmActionClient()  
    armAction_client.SetTimeout(10.0)
    armAction_client.Init()

    # actionList = armAction_client.GetActionList()
    # print("actionList\n",actionList)

    if args.auto_action is not None:
        print(f"Auto mode: action id {args.auto_action}, period {args.period}s")
        while True:
            run_action(armAction_client, args.auto_action)
            time.sleep(args.period)

    print("Input \"list\" to list all test option ...")
    while True:
        user_interface.terminal_handle()

        print(f"Updated Test Option: Name = {test_option.name}, ID = {test_option.id}")
        run_action(armAction_client, test_option.id)

        time.sleep(1)
