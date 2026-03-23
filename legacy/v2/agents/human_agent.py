class HumanAgent:
    """Human-controlled agent for Pokemon TCG Pocket battles via terminal input"""
    
    def __init__(self, player):
        self.player = player
        self.is_human = True

    def play_action(self, actions):
        """Play an action from the list of actions"""
        print("Available actions:")
        for i, action in enumerate(actions):
            print(f"    {i}: {action}")
            
        while True:
            try:
                action_index = int(input("Enter the number of the action you want to play: "))
                if 0 <= action_index < len(actions):
                    self.player.play_card(actions[action_index])
                    break
                else:
                    print("Invalid action number. Please enter a number between 0 and", len(actions)-1)
                    print("\nAvailable actions:")
                    for i, action in enumerate(actions):
                        print(f"    {i}: {action}")
            except ValueError:
                print("Please enter a valid number.")
                print("\nAvailable actions:")
                for i, action in enumerate(actions):
                    print(f"    {i}: {action}")
