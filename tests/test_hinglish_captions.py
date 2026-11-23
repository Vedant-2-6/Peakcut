"""Tests for Chunk 2: Caption reliability for English with accents, Hindi, and code-switched Hinglish."""
import os
import sys
import tempfile

os.environ["PEAKCUT_DATA"] = tempfile.mkdtemp(prefix="pc-hinglish-")
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")

from studio import brain, roman

fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  {extra}" if extra and not ok else ""))
    if not ok:
        fails.append(name)


def ws(text):
    return [{"w": w, "s": round(i * 0.5, 2), "e": round(i * 0.5 + 0.4, 2)} for i, w in enumerate(text.split())]


def text(words):
    return " ".join(w["w"] for w in words)


# 1. roman.is_hinglish detection
check("detects Devanagari as Hinglish", roman.is_hinglish("क्या हाल है"))
check("detects Urdu script as Hinglish", roman.is_hinglish("کیا حال ہے"))
check("detects Roman Hinglish keywords in words list", roman.is_hinglish(ws("bhai revive kar de jaldi")))
check("detects Roman Hinglish single string", roman.is_hinglish("arre yaar kya kar raha hai"))
check("detects Hinglish via title hints", roman.is_hinglish(ws("welcome to stream guys"), title="BGMI LIVE STREAM | MORTAL"))
check("detects Hinglish via phonetic mishearing in words", roman.is_hinglish(ws("array bye deck this out")))
check("pure English without hints is not Hinglish", not roman.is_hinglish(ws("welcome back today we build a redstone machine in minecraft"), title="Minecraft Survival Ep 10"))

# 2. roman.is_phonetic_variant
check("phonetic pair: array -> arre", roman.is_phonetic_variant("array", "arre"))
check("phonetic pair: pie -> bhai", roman.is_phonetic_variant("pie", "bhai"))
check("phonetic pair: bye -> bhai", roman.is_phonetic_variant("bye", "bhai"))
check("phonetic pair: mud -> matlab", roman.is_phonetic_variant("mud", "matlab"))
check("phonetic pair: take -> theek", roman.is_phonetic_variant("take", "theek"))
check("phonetic pair: night -> nahi", roman.is_phonetic_variant("night", "nahi"))
check("phonetic pair: can -> kya", roman.is_phonetic_variant("can", "kya"))
check("phonetic pair: deck -> dekh", roman.is_phonetic_variant("deck", "dekh"))
check("phonetic pair: car -> kar", roman.is_phonetic_variant("car", "kar"))
check("phonetic pair: shallow -> chalo", roman.is_phonetic_variant("shallow", "chalo"))
check("unrelated words are not phonetic variants", not roman.is_phonetic_variant("banana", "spaceship"))
check("unrelated word to Hinglish word is rejected", not roman.is_phonetic_variant("elephant", "bhai"))

# 3. brain._same_word with Hinglish corrections
check("_same_word preserves exact word", brain._same_word("hello", "Hello"))
check("_same_word accepts digits", brain._same_word("twenty", "20"))
check("_same_word accepts SequenceMatcher typos", brain._same_word("runing", "running"))
check("_same_word accepts Hinglish phonetic correction: pie -> bhai", brain._same_word("pie", "bhai"))
check("_same_word accepts Hinglish phonetic correction: take -> theek", brain._same_word("take", "theek"))
check("_same_word accepts Hinglish phonetic correction: mud -> matlab", brain._same_word("mud", "matlab"))
check("_same_word accepts Hinglish phonetic correction: night -> nahi", brain._same_word("night", "nahi"))
check("_same_word rejects complete hallucination", not brain._same_word("store", "subscribe to my youtube channel"))

# 4. brain.fix_caption_words with simulated Ollama / LLM responses
answers = {}


def mock_ai(prompt, schema=None, purpose=""):
    return answers["response"], "mock-model", 10


brain.ask_ai = mock_ai

# Simulated ASR mishearings of Indian gaming stream:
# Spoken: "Arre bhai revive kar de jaldi theek hai"
# ASR heard: "array pie revive car de jolly take hai"
asr_words = ws("array pie revive car the jolly take hai")
answers["response"] = ["Arre", "bhai", "revive", "kar", "de", "jaldi", "theek", "hai"]
fixed = brain.fix_caption_words(asr_words, title="BGMI CLUTCH GAMEPLAY")
check("ASR phonetic mishearings properly corrected to Hinglish in captions",
      text(fixed) == "Arre bhai revive kar de jaldi theek hai",
      text(fixed))
check("timings accurately preserved on every word",
      [(w["s"], w["e"]) for w in fixed] == [(w["s"], w["e"]) for w in asr_words])

# Pure English video remains natural and preserves punctuation
en_words = ws("hello everyone welcome back to the channel")
answers["response"] = ["Hello", "everyone,", "welcome", "back", "to", "the", "channel."]
fixed_en = brain.fix_caption_words(en_words, title="Minecraft Episode 1")
check("pure English captions preserve proper casing and punctuation",
      text(fixed_en) == "Hello everyone, welcome back to the channel.",
      text(fixed_en))

# Devanagari translation refusal is preserved
hi_words = ws("चूना लगा")
answers["response"] = ["lime", "applied"]  # unwanted translation
fixed_hi = brain.fix_caption_words(hi_words, title="comedy")
check("Devanagari translation refusal is preserved and Romanized",
      text(fixed_hi) == "chuna laga",
      text(fixed_hi))

print("ALL HINGLISH CAPTION TESTS PASSED" if not fails else f"{len(fails)} test(s) failed")
import shutil

shutil.rmtree(os.environ["PEAKCUT_DATA"], ignore_errors=True)
sys.exit(1 if fails else 0)
