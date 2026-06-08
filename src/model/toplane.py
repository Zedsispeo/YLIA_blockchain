class toplane :
    def __init__(self, version, timestamp, previous_hash, merkle_root, txcount, author, index):
        self.version = version
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.merkle_root = merkle_root
        self.txcount = txcount
        self.author = author
        self.index = index

    def __str__(self):
        return f"Header(version={self.version}, timestamp={self.timestamp}, previous_hash={self.previous_hash}, merkle_root={self.merkle_root}, txcount={self.txcount}, author={self.author}, index={self.index})"