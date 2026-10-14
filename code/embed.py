"""Embed title+abstract with one of the candidate models; cache to models/<name>/<set>.npy.

Usage: embed.py MODEL SET   (SET = positives | astroph)
Rows are aligned with data/<SET>.json. Vectors are L2-normalized float16.
"""
import json, os, sys, time
import numpy as np
import torch

ROOT = os.path.join(os.path.dirname(__file__), "..")
MODELS = {
    "specter2": "allenai/specter2",
    "indus": "nasa-impact/nasa-smd-ibm-st-v2",
    "bge": "BAAI/bge-base-en-v1.5",
    "qwen3": "Qwen/Qwen3-Embedding-0.6B",
}


DEVICE = os.environ.get("ARXIVSORT_DEVICE") or ("mps" if torch.backends.mps.is_available() else "cpu")
DTYPE = torch.float16 if DEVICE == "mps" else torch.float32  # half precision is only a speed-up on the Apple GPU


def load(name):
    if name == "specter2":
        from transformers import AutoTokenizer
        from adapters import AutoAdapterModel
        tok = AutoTokenizer.from_pretrained("allenai/specter2_base")
        m = AutoAdapterModel.from_pretrained("allenai/specter2_base")
        m.load_adapter("allenai/specter2", source="hf", load_as="specter2", set_active=True)
        m.set_active_adapters("specter2")
        m.to(DEVICE).to(DTYPE).eval()

        def enc(titles, abstracts, bs=32):
            out = []
            texts = [t + tok.sep_token + a for t, a in zip(titles, abstracts)]
            with torch.no_grad():
                for i in range(0, len(texts), bs):
                    x = tok(texts[i:i + bs], padding=True, truncation=True, max_length=512,
                            return_tensors="pt", return_token_type_ids=False).to(DEVICE)
                    out.append(m(**x).last_hidden_state[:, 0, :].float().cpu().numpy())
            return np.vstack(out)
        return enc
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(MODELS[name], device=DEVICE, model_kwargs={"dtype": DTYPE})
    m.max_seq_length = 512

    def enc(titles, abstracts, bs=32):
        return m.encode([t + ". " + a for t, a in zip(titles, abstracts)], batch_size=bs)
    return enc


def text_fields(rows):
    return [r["title"] for r in rows], [r.get("abstract", "") for r in rows]


if __name__ == "__main__":
    name, which = sys.argv[1], sys.argv[2]
    rows = json.load(open(os.path.join(ROOT, "data", which + ".json")))
    os.makedirs(os.path.join(ROOT, "models", name), exist_ok=True)
    path = os.path.join(ROOT, "models", name, which + ".npy")
    enc = load(name)
    t0 = time.time()
    titles, abstracts = text_fields(rows)
    # sort by length so batches pad little; restore order afterwards
    order = np.argsort([len(t) + len(a) for t, a in zip(titles, abstracts)])
    vecs = np.zeros((len(rows), 0), dtype=np.float32)
    parts = []
    CH = 4096
    for i in range(0, len(order), CH):
        idx = order[i:i + CH]
        parts.append(enc([titles[j] for j in idx], [abstracts[j] for j in idx]))
        print(f"{name}/{which}: {min(i + CH, len(order))}/{len(order)} ({time.time() - t0:.0f}s)", flush=True)
    E = np.vstack(parts)
    vecs = np.empty_like(E)
    vecs[order] = E
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    np.save(path, vecs.astype(np.float16))
    print("saved", path, vecs.shape, f"{time.time() - t0:.0f}s")
