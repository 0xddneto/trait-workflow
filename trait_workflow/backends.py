"""Backends de geracao de imagem. Todos recebem a base composta e devolvem
bytes PNG do personagem vestido/decorado. A protecao da base NAO depende
deles: e imposta depois, na extracao deterministica."""

import base64
import json
import os
from pathlib import Path

import requests

KEYS_FILE = Path.home() / ".trait-workflow" / "keys.json"

GEMINI_MODELS = ["gemini-3.1-flash-image", "gemini-2.5-flash-image"]
FAL_DEFAULT_MODEL = "fal-ai/flux-pro/v1/fill"

GUARD_SUFFIX = (
    " Keep the exact same character, pose, proportions, art style, camera "
    "framing and plain white background. Do not move, resize or redraw any "
    "other part of the image."
)


def get_key(name, env):
    v = os.environ.get(env)
    if v:
        return v
    if KEYS_FILE.exists():
        data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
        if data.get(name):
            return data[name]
    raise RuntimeError(
        f"Credencial ausente: defina a variavel {env} ou a chave '{name}' em {KEYS_FILE}"
    )


def _png_b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def _data_uri(path):
    return "data:image/png;base64," + _png_b64(path)


def generate_gemini(prompt, image_path, model=None, timeout=180):
    key = get_key("gemini", "GEMINI_API_KEY")
    models = [model] if model else GEMINI_MODELS
    errors = []
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        body = {
            "contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": _png_b64(image_path)}},
            ]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        r = requests.post(url, params={"key": key}, json=body, timeout=timeout)
        if r.status_code != 200:
            errors.append(f"{m}: HTTP {r.status_code} {r.text[:300]}")
            continue
        data = r.json()
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                blob = part.get("inlineData") or part.get("inline_data")
                if blob and blob.get("data"):
                    return base64.b64decode(blob["data"])
        errors.append(f"{m}: resposta sem imagem ({json.dumps(data)[:300]})")
    raise RuntimeError("Gemini nao retornou imagem. Erros: " + " | ".join(errors))


def generate_fal(prompt, image_path, mask_path=None, model=None, timeout=300):
    """FLUX Fill (inpainting com mascara real): so repinta dentro da mascara."""
    key = get_key("fal", "FAL_KEY")
    model = model or FAL_DEFAULT_MODEL
    payload = {"prompt": prompt, "image_url": _data_uri(image_path), "sync_mode": True}
    if mask_path:
        payload["mask_url"] = _data_uri(mask_path)
    r = requests.post(
        f"https://fal.run/{model}",
        headers={"Authorization": f"Key {key}"},
        json=payload,
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"fal {model}: HTTP {r.status_code} {r.text[:300]}")
    data = r.json()
    imgs = data.get("images") or ([data["image"]] if data.get("image") else [])
    if not imgs:
        raise RuntimeError(f"fal {model}: resposta sem imagens ({json.dumps(data)[:300]})")
    url = imgs[0]["url"] if isinstance(imgs[0], dict) else imgs[0]
    if url.startswith("data:"):
        return base64.b64decode(url.split(",", 1)[1])
    return requests.get(url, timeout=60).content


CF_DEFAULT_MODEL = "@cf/runwayml/stable-diffusion-v1-5-inpainting"
CF_SIZE = 512  # resolucao nativa do SD 1.5


def generate_cloudflare(prompt, image_path, mask_path=None, model=None,
                        timeout=180):
    """Inpainting gratuito (Workers AI). Reduz para 512 na entrada; a
    extracao redimensiona de volta para o canvas da base."""
    import io

    from PIL import Image

    token = get_key("cloudflare_token", "CLOUDFLARE_API_TOKEN")
    account = get_key("cloudflare_account", "CLOUDFLARE_ACCOUNT_ID")
    model = model or CF_DEFAULT_MODEL

    def _small_bytes(path, mode):
        im = Image.open(path).convert(mode)
        im = im.resize((CF_SIZE, CF_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return list(buf.getvalue())

    payload = {
        "prompt": prompt,
        "image": _small_bytes(image_path, "RGB"),
        "num_steps": 20,
        "strength": 1.0,
        "guidance": 7.5,
    }
    if mask_path:
        payload["mask"] = _small_bytes(mask_path, "L")
    r = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload, timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"cloudflare {model}: HTTP {r.status_code} {r.text[:300]}")
    ctype = r.headers.get("content-type", "")
    if "image" not in ctype and not r.content.startswith(b"\x89PNG"):
        raise RuntimeError(f"cloudflare {model}: resposta nao-imagem ({r.text[:300]})")
    return r.content


def generate(backend, prompt, image_path, mask_path=None, model=None, guard=True):
    if guard:
        prompt = prompt.rstrip(". ") + "." + GUARD_SUFFIX
    if backend == "gemini":
        return generate_gemini(prompt, image_path, model=model)
    if backend == "fal":
        return generate_fal(prompt, image_path, mask_path=mask_path, model=model)
    if backend in ("cloudflare", "cf"):
        return generate_cloudflare(prompt, image_path, mask_path=mask_path,
                                   model=model)
    raise ValueError(
        f"backend desconhecido: {backend} (use 'gemini', 'fal' ou 'cloudflare')")
