import torch
import torch.nn as nn
import torch.nn.functional as F

class MLP(nn.Module):
    def __init__(self, inp: int, hid: int, emb: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(inp, hid),
            nn.ReLU(),
            nn.Linear(hid, emb),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.normalize(self.net(x), dim=1)

class Model(nn.Module):
    def __init__(self, inp: int, hidden: int, embed: int):
        super().__init__()
        self.p = MLP(inp, hidden, embed)
        self.d = MLP(inp, hidden, embed)

    def encode_patient(self, x: torch.Tensor) -> torch.Tensor:
        return self.p(x)

    def encode_disease(self, x: torch.Tensor) -> torch.Tensor:
        return self.d(x)
