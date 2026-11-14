#!/usr/bin/env python3
"""
gpt.py - train a small GPT-style language model from scratch.

Modern pieces: RMSNorm, rotary position embeddings (RoPE), SwiGLU MLP,
tied embeddings, flash attention (via PyTorch SDPA), AdamW + cosine LR.

Usage:
  pip install torch tokenizers
  python gpt.py train --size tiny  --tokenizer char            # CPU-friendly smoke test
  python gpt.py train --size small --tokenizer bpe --data my.txt
  python gpt.py generate --out out --prompt "Once upon a time"
"""
import argparse
import contextlib
import json
import math
import os
import time
import urllib.request
from dataclasses import dataclass, asdict

import torch
import torch.nn as nn
import torch.nn.functional as F

SHAKESPEARE_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"

PRESETS = {  # approx. params: tiny ~1M, small ~11M (+embeddings), medium ~85M (+embeddings)
    "tiny": dict(n_layer=4, n_head=4, n_embd=128, block_size=128),
    "small": dict(n_layer=6, n_head=6, n_embd=384, block_size=256),
    "medium": dict(n_layer=12, n_head=12, n_embd=768, block_size=512),
}


# --------------------------------------------------------------------------
# Tokenizers
# --------------------------------------------------------------------------
class CharTokenizer:
    """One token per character. Simplest possible tokenizer; great for tiny data."""

    def __init__(self, chars):
        self.chars = list(chars)
        self.stoi = {c: i for i, c in enumerate(self.chars)}

    @property
    def vocab_size(self):
        return len(self.chars)

    @classmethod
    def train(cls, text):
        return cls(sorted(set(text)))

    def encode(self, s):
        return [self.stoi[c] for c in s if c in self.stoi]

    def decode(self, ids):
        return "".join(self.chars[i] for i in ids)

    def to_dict(self):
        return {"type": "char", "chars": self.chars}


class BPETokenizer:
    """Byte-level BPE trained on your own data (HuggingFace `tokenizers`)."""

    def __init__(self, hf):
        self.hf = hf

    @property
    def vocab_size(self):
        return self.hf.get_vocab_size()

    @classmethod
    def train(cls, text, vocab_size):
        from tokenizers import Tokenizer, models, trainers, pre_tokenizers, decoders

        tok = Tokenizer(models.BPE())
        tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
        tok.decoder = decoders.ByteLevel()
        trainer = trainers.BpeTrainer(
            vocab_size=vocab_size,
            special_tokens=["<|endoftext|>"],
            initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        )
        chunks = (text[i:i + 10_000] for i in range(0, len(text), 10_000))
        tok.train_from_iterator(chunks, trainer)
        return cls(tok)

    def encode(self, s):
        return self.hf.encode(s).ids

    def decode(self, ids):
        return self.hf.decode(ids)

    def to_dict(self):
        return {"type": "bpe", "hf": self.hf.to_str()}


def save_tokenizer(tok, out_dir):
    with open(os.path.join(out_dir, "tokenizer.json"), "w") as f:
        json.dump(tok.to_dict(), f)


def load_tokenizer(out_dir):
    with open(os.path.join(out_dir, "tokenizer.json")) as f:
        d = json.load(f)
    if d["type"] == "char":
        return CharTokenizer(d["chars"])
    from tokenizers import Tokenizer
    return BPETokenizer(Tokenizer.from_str(d["hf"]))


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
@dataclass
class Config:
    vocab_size: int = 0
    block_size: int = 256
    n_layer: int = 6
    n_head: int = 6
    n_embd: int = 384
    dropout: float = 0.1


class RMSNorm(nn.Module):
    def __init__(self, dim, eps=1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        xf = x.float()
        xf = xf * torch.rsqrt(xf.pow(2).mean(-1, keepdim=True) + self.eps)
        return xf.type_as(x) * self.weight


def rope_cache(seq_len, head_dim, base=10000.0):
    inv_freq = 1.0 / (base ** (torch.arange(0, head_dim, 2).float() / head_dim))
    t = torch.arange(seq_len).float()
    freqs = torch.outer(t, inv_freq)  # (T, head_dim/2)
    return freqs.cos(), freqs.sin()


def apply_rope(x, cos, sin):
    # x: (B, H, T, head_dim); rotate consecutive pairs of channels by position-dependent angles
    T = x.size(2)
    cos, sin = cos[:T], sin[:T]
    x1, x2 = x[..., 0::2], x[..., 1::2]
    y1 = x1 * cos - x2 * sin
    y2 = x1 * sin + x2 * cos
    return torch.stack((y1, y2), dim=-1).flatten(-2).type_as(x)


class Attention(nn.Module):
    def __init__(self, c):
        super().__init__()
        assert c.n_embd % c.n_head == 0
        self.n_head = c.n_head
        self.head_dim = c.n_embd // c.n_head
        self.qkv = nn.Linear(c.n_embd, 3 * c.n_embd, bias=False)
        self.proj = nn.Linear(c.n_embd, c.n_embd, bias=False)
        self.dropout = c.dropout

    def forward(self, x, cos, sin):
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        q, k = apply_rope(q, cos, sin), apply_rope(k, cos, sin)
        y = F.scaled_dot_product_attention(
            q, k, v, is_causal=True, dropout_p=self.dropout if self.training else 0.0
        )
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(y)


class MLP(nn.Module):
    """SwiGLU feed-forward."""

    def __init__(self, c):
        super().__init__()
        hidden = int(8 * c.n_embd / 3)
        hidden = 64 * ((hidden + 63) // 64)
        self.w1 = nn.Linear(c.n_embd, hidden, bias=False)  # gate
        self.w2 = nn.Linear(c.n_embd, hidden, bias=False)  # value
        self.w3 = nn.Linear(hidden, c.n_embd, bias=False)  # output
        self.drop = nn.Dropout(c.dropout)

    def forward(self, x):
        return self.drop(self.w3(F.silu(self.w1(x)) * self.w2(x)))


class Block(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.norm1 = RMSNorm(c.n_embd)
        self.attn = Attention(c)
        self.norm2 = RMSNorm(c.n_embd)
        self.mlp = MLP(c)

    def forward(self, x, cos, sin):
        x = x + self.attn(self.norm1(x), cos, sin)
        x = x + self.mlp(self.norm2(x))
        return x


class GPT(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.c = c
        self.tok = nn.Embedding(c.vocab_size, c.n_embd)
        self.drop = nn.Dropout(c.dropout)
        self.blocks = nn.ModuleList([Block(c) for _ in range(c.n_layer)])
        self.norm = RMSNorm(c.n_embd)
        self.head = nn.Linear(c.n_embd, c.vocab_size, bias=False)
        self.head.weight = self.tok.weight  # weight tying
        cos, sin = rope_cache(c.block_size, c.n_embd // c.n_head)
        self.register_buffer("cos", cos, persistent=False)
        self.register_buffer("sin", sin, persistent=False)

        self.apply(self._init)
        # scale residual-output projections (GPT-2 style)
        for name, p in self.named_parameters():
            if name.endswith("proj.weight") or name.endswith("w3.weight"):
                nn.init.normal_(p, mean=0.0, std=0.02 / math.sqrt(2 * c.n_layer))

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)

    def forward(self, idx, targets=None):
        x = self.drop(self.tok(idx))
        for blk in self.blocks:
            x = blk(x, self.cos, self.sin)
        logits = self.head(self.norm(x))
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss

    @torch.no_grad()
    def generate(self, idx, max_new_tokens, temperature=0.8, top_k=50):
        for _ in range(max_new_tokens):
            ctx = idx[:, -self.c.block_size:]
            logits, _ = self(ctx)
            logits = logits[:, -1, :] / max(temperature, 1e-5)
            if top_k:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = -float("inf")
            probs = F.softmax(logits, dim=-1)
            idx = torch.cat([idx, torch.multinomial(probs, 1)], dim=1)
        return idx


# --------------------------------------------------------------------------
# Training
# --------------------------------------------------------------------------
def pick_device():
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_text(path):
    if path is None:
        path = "shakespeare.txt"
        if not os.path.exists(path):
            print(f"No --data given; downloading tiny Shakespeare to {path} ...")
            urllib.request.urlretrieve(SHAKESPEARE_URL, path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_batch(data, batch_size, block_size, device):
    ix = torch.randint(len(data) - block_size - 1, (batch_size,))
    x = torch.stack([data[i:i + block_size] for i in ix])
    y = torch.stack([data[i + 1:i + 1 + block_size] for i in ix])
    return x.to(device), y.to(device)


@torch.no_grad()
def estimate_loss(model, splits, a, block_size, device, ctx):
    model.eval()
    out = {}
    for name, data in splits.items():
        losses = torch.zeros(a.eval_iters)
        for k in range(a.eval_iters):
            x, y = get_batch(data, a.batch_size, block_size, device)
            with ctx:
                _, loss = model(x, y)
            losses[k] = loss.item()
        out[name] = losses.mean().item()
    model.train()
    return out


def sample_text(model, tok, device, n=300, prompt="\n"):
    model.eval()
    ids = tok.encode(prompt) or [0]
    idx = torch.tensor([ids], dtype=torch.long, device=device)
    out = model.generate(idx, n)[0].tolist()
    model.train()
    return tok.decode(out)


def cmd_train(a):
    torch.manual_seed(a.seed)
    device = pick_device()
    os.makedirs(a.out, exist_ok=True)
    ckpt_path = os.path.join(a.out, "ckpt.pt")
    print(f"device: {device}")

    text = load_text(a.data)
    print(f"dataset: {len(text):,} characters")

    ckpt = torch.load(ckpt_path, map_location=device) if (a.resume and os.path.exists(ckpt_path)) else None

    if ckpt:
        tok = load_tokenizer(a.out)
        cfg = Config(**ckpt["config"])
    else:
        tok = CharTokenizer.train(text) if a.tokenizer == "char" else BPETokenizer.train(text, a.vocab_size)
        save_tokenizer(tok, a.out)
        cfg = Config(vocab_size=tok.vocab_size, dropout=a.dropout, **PRESETS[a.size])
    print(f"vocab size: {cfg.vocab_size}")

    ids = torch.tensor(tok.encode(text), dtype=torch.long)
    n_val = max(int(0.1 * len(ids)), cfg.block_size + 2)
    splits = {"train": ids[:-n_val], "val": ids[-n_val:]}
    print(f"tokens: {len(ids):,} (train {len(splits['train']):,} / val {len(splits['val']):,})")

    model = GPT(cfg).to(device)
    print(f"parameters: {sum(p.numel() for p in model.parameters()) / 1e6:.2f}M")

    # optimizer: weight decay only on matrices (not norms/embeddings' 1-D params)
    decay = [p for p in model.parameters() if p.dim() >= 2]
    no_decay = [p for p in model.parameters() if p.dim() < 2]
    opt = torch.optim.AdamW(
        [{"params": decay, "weight_decay": 0.1}, {"params": no_decay, "weight_decay": 0.0}],
        lr=a.lr, betas=(0.9, 0.95), fused=(device == "cuda"),
    )

    start_iter, best_val = 0, float("inf")
    if ckpt:
        model.load_state_dict(ckpt["model"])
        opt.load_state_dict(ckpt["opt"])
        start_iter = ckpt["iter"]
        best_val = float("inf") if a.reset_best else ckpt["best_val"]
        print(f"resumed from iter {start_iter}")

    # mixed precision on CUDA
    if device == "cuda":
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        ctx = torch.autocast("cuda", dtype=dtype)
        scaler = torch.amp.GradScaler("cuda", enabled=(dtype == torch.float16))
    else:
        ctx = contextlib.nullcontext()
        scaler = torch.amp.GradScaler("cuda", enabled=False)

    train_model = torch.compile(model) if a.compile else model
    min_lr = a.lr / 10

    def get_lr(it):
        if it < a.warmup:
            return a.lr * (it + 1) / a.warmup
        progress = (it - a.warmup) / max(1, a.max_iters - a.warmup)
        return min_lr + 0.5 * (1 + math.cos(math.pi * progress)) * (a.lr - min_lr)

    t0 = time.time()
    model.train()
    for it in range(start_iter, a.max_iters + 1):
        lr = get_lr(it)
        for g in opt.param_groups:
            g["lr"] = lr

        if it % a.eval_interval == 0:
            losses = estimate_loss(model, splits, a, cfg.block_size, device, ctx)
            print(f"\n[eval] iter {it}: train {losses['train']:.4f} | val {losses['val']:.4f}")
            if losses["val"] < best_val:
                best_val = losses["val"]
                torch.save({"model": model.state_dict(), "opt": opt.state_dict(),
                            "config": asdict(cfg), "iter": it, "best_val": best_val}, ckpt_path)
                print(f"  saved checkpoint (best val {best_val:.4f})")
            print("--- sample ---")
            print(sample_text(model, tok, device, n=200))
            print("--------------")

        if it == a.max_iters:
            break

        for _ in range(a.grad_accum):
            x, y = get_batch(splits["train"], a.batch_size, cfg.block_size, device)
            with ctx:
                _, loss = train_model(x, y)
            scaler.scale(loss / a.grad_accum).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        opt.zero_grad(set_to_none=True)

        if it % 50 == 0:
            dt = time.time() - t0
            t0 = time.time()
            print(f"iter {it:6d} | loss {loss.item():.4f} | lr {lr:.2e} | {dt:.1f}s/50 it")

    print(f"\nDone. Best val loss {best_val:.4f}. Checkpoint: {ckpt_path}")


def cmd_generate(a):
    device = pick_device()
    ckpt = torch.load(os.path.join(a.out, "ckpt.pt"), map_location=device)
    tok = load_tokenizer(a.out)
    model = GPT(Config(**ckpt["config"])).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    ids = tok.encode(a.prompt) or [0]
    idx = torch.tensor([ids], dtype=torch.long, device=device)
    out = model.generate(idx, a.tokens, a.temperature, a.top_k)[0].tolist()
    print(tok.decode(out))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("train")
    t.add_argument("--data", default=None, help="path to a UTF-8 .txt file (default: tiny Shakespeare)")
    t.add_argument("--out", default="out")
    t.add_argument("--size", choices=PRESETS, default="small")
    t.add_argument("--tokenizer", choices=["char", "bpe"], default="char")
    t.add_argument("--vocab_size", type=int, default=2048, help="BPE vocab size")
    t.add_argument("--batch_size", type=int, default=32)
    t.add_argument("--grad_accum", type=int, default=1)
    t.add_argument("--lr", type=float, default=6e-4)
    t.add_argument("--warmup", type=int, default=100)
    t.add_argument("--max_iters", type=int, default=3000)
    t.add_argument("--eval_interval", type=int, default=250)
    t.add_argument("--eval_iters", type=int, default=20)
    t.add_argument("--dropout", type=float, default=0.1)
    t.add_argument("--compile", action="store_true", help="torch.compile (faster on CUDA)")
    t.add_argument("--resume", action="store_true")
    t.add_argument("--reset_best", action="store_true",
                   help="with --resume: forget the old best val loss (use when the dataset changed)")
    t.add_argument("--seed", type=int, default=1337)
    t.set_defaults(fn=cmd_train)

    g = sub.add_parser("generate")
    g.add_argument("--out", default="out")
    g.add_argument("--prompt", default="\n")
    g.add_argument("--tokens", type=int, default=300)
    g.add_argument("--temperature", type=float, default=0.8)
    g.add_argument("--top_k", type=int, default=50)
    g.set_defaults(fn=cmd_generate)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
