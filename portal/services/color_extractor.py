"""Extracts dominant brand colors from a logo image using Pillow k-means."""
import json
from pathlib import Path
from PIL import Image
import colorsys


def rgb_to_hex(r, g, b) -> str:
    return "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))


def is_boring(r, g, b, threshold=30) -> bool:
    """Skip near-white, near-black, and near-grey pixels."""
    if r > 225 and g > 225 and b > 225:   return True  # white
    if r < 30  and g < 30  and b < 30:    return True  # black
    max_c, min_c = max(r, g, b), min(r, g, b)
    if (max_c - min_c) < threshold:       return True  # grey
    return False


def kmeans_colors(pixels: list[tuple], k=5, iterations=10) -> list[tuple]:
    """Simple k-means on RGB pixels. Returns k centroids."""
    import random
    if not pixels:
        return []
    k = min(k, len(pixels))
    centers = random.sample(pixels, k)
    for _ in range(iterations):
        clusters = [[] for _ in range(k)]
        for p in pixels:
            dists = [sum((p[i]-c[i])**2 for i in range(3)) for c in centers]
            clusters[dists.index(min(dists))].append(p)
        new_centers = []
        for cluster in clusters:
            if cluster:
                n = len(cluster)
                new_centers.append(tuple(sum(p[i] for p in cluster)//n for i in range(3)))
            else:
                new_centers.append(random.choice(pixels))
        centers = new_centers
    # Sort by cluster size (dominant first)
    counts = [0] * k
    for p in pixels:
        dists = [sum((p[i]-c[i])**2 for i in range(3)) for c in centers]
        counts[dists.index(min(dists))] += 1
    sorted_centers = [c for _, c in sorted(zip(counts, centers), reverse=True)]
    return sorted_centers


def extract_colors(logo_path: Path, output_path: Path) -> dict:
    result = {
        "dominant": "#2B5EA7",
        "palette": [],
        "background_suggestion": "#F8F9FA",
        "text_suggestion": "#1A1A1A",
        "accent_suggestion": "#2B5EA7",
        "extraction_method": "default",
        "source_image": str(logo_path.name),
    }

    if not logo_path.exists():
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    try:
        img = Image.open(str(logo_path)).convert("RGBA")
        img = img.resize((120, 120), Image.LANCZOS)

        pixels = []
        for r, g, b, a in img.getdata():
            if a > 128 and not is_boring(r, g, b):
                pixels.append((r, g, b))

        if len(pixels) < 10:
            # Relax boring filter
            pixels = [(r, g, b) for r, g, b, a in img.getdata() if a > 100]

        if not pixels:
            output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result

        centers = kmeans_colors(pixels, k=5, iterations=12)
        palette = [rgb_to_hex(*c) for c in centers]

        if palette:
            result["dominant"]  = palette[0]
            result["palette"]   = palette
            result["accent_suggestion"] = palette[0]
            # Suggest light background if dominant is dark, dark text, and vice versa
            r0, g0, b0 = centers[0]
            luminance = (0.299*r0 + 0.587*g0 + 0.114*b0) / 255
            if luminance > 0.5:
                result["background_suggestion"] = "#1A1A2E"
                result["text_suggestion"]       = "#FFFFFF"
            else:
                result["background_suggestion"] = "#F8F9FA"
                result["text_suggestion"]       = "#1A1A1A"
            result["extraction_method"] = "pillow_kmeans"

    except Exception as e:
        result["error"] = str(e)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
