class midlane:
    def __init__(self, etablissement, signature, hash):
        self.etablissement = etablissement
        self.signature = signature
        self.hash = hash
    
    def __str__(self):
        return f"midlane(etablissement={self.etablissement}, signature={self.signature}, hash={self.hash})"