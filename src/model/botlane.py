class botlane:
    def __init__(self, transactions):
        self.transactions : list[transaction] = transactions

    def __str__(self):
        return f"botlane(transactions={self.transactions})"