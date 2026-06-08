class transaction:
    def __init__(self, type, amount, etablissement, client, timestamp, signature, hash):
        self.type = type
        self.amount = amount
        self.etablissement = etablissement
        self.client = client
        self.timestamp = timestamp
        self.signature = signature
        self.hash = hash

    def __str__(self):
        return f"transaction(type={self.type}, amount={self.amount}, etablissement={self.etablissement}, client={self.client}, timestamp={self.timestamp}, signature={self.signature}, hash={self.hash})"