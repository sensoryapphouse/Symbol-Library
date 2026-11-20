#!/usr/bin/env python3
"""Roll out DO_TENSES.MD across Fleximbols/Verbs: for every BASE verb file, create past / future /
present-continuous forms = the base image + the matching PiCom clock (tense_annotate.annotate).
Naming (per spec): past=<verb>ed / irregular, continuous=<verb>ing, future='will <verb>'. Phrases
conjugate the HEAD word, keep the rest. Existing tense files: if a renamed copy of the base -> stamp
clock in place; if a genuinely different artist pose -> leave alone. Skip files that are already
tense forms. Both (M)/(F)/genderless.
Run: python3 build_tenses.py            # dry-run: counts + sample conjugations
     python3 build_tenses.py --sample   # write ~8 varied examples to /tmp/tense_s + montage list
     python3 build_tenses.py --apply     # write into Verbs/ (manifest saved)
"""
import os, re, glob, sys, hashlib, json
sys.path.insert(0, "/Users/paulblenkhorn/Desktop/picom_review")
import tense_annotate as TA

VERBS = "/Users/paulblenkhorn/Desktop/Fleximbols/Verbs"
VOW = set("aeiou")
CONS = lambda c: c.isalpha() and c not in VOW

IRREG = {
 "go":"went","eat":"ate","run":"ran","sit":"sat","swim":"swam","drink":"drank","sing":"sang",
 "ring":"rang","write":"wrote","ride":"rode","drive":"drove","throw":"threw","grow":"grew",
 "know":"knew","fly":"flew","draw":"drew","catch":"caught","teach":"taught","buy":"bought",
 "bring":"brought","think":"thought","fight":"fought","seek":"sought","sleep":"slept","keep":"kept",
 "feel":"felt","meet":"met","leave":"left","lose":"lost","make":"made","take":"took","shake":"shook",
 "give":"gave","forgive":"forgave","come":"came","become":"became","see":"saw","say":"said",
 "pay":"paid","lay":"laid","tell":"told","sell":"sold","hold":"held","build":"built","send":"sent",
 "spend":"spent","lend":"lent","bend":"bent","feed":"fed","lead":"led","read":"read","hear":"heard",
 "hide":"hid","bite":"bit","hit":"hit","cut":"cut","put":"put","let":"let","set":"set","shut":"shut",
 "cost":"cost","hurt":"hurt","get":"got","forget":"forgot","begin":"began","break":"broke",
 "speak":"spoke","wake":"woke","choose":"chose","freeze":"froze","wear":"wore","tear":"tore",
 "swear":"swore","blow":"blew","stand":"stood","understand":"understood","win":"won","spin":"spun",
 "dig":"dug","stick":"stuck","sting":"stung","swing":"swung","hang":"hung","strike":"struck",
 "find":"found","bind":"bound","sink":"sank","shrink":"shrank","sweep":"swept","weep":"wept",
 "creep":"crept","kneel":"knelt","mean":"meant","deal":"dealt","do":"did","have":"had","fall":"fell",
 "flee":"fled","fling":"flung","light":"lit","spread":"spread","cast":"cast","burst":"burst",
 "slide":"slid","shoot":"shot","wind":"wound","tie":"tied","wring":"wrung","sling":"slung",
 "spit":"spat","quit":"quit","bet":"bet","knit":"knit","wet":"wet","split":"split","slit":"slit",
 "rid":"rid","upset":"upset","withdraw":"withdrew","overcome":"overcame","sweep":"swept",
}
DOUBLE = set("begin forget prefer refer occur permit admit control patrol commit submit regret "
             "prefer transfer propel rebel compel expel repel shred".split())
NODOUBLE = set("visit open enter offer answer order cover differ suffer gather deliver enter "
               "listen happen".split())

def cvc(h):
    if len(h) < 3: return False
    a,b,c = h[-3],h[-2],h[-1]
    return CONS(a) and (b in VOW) and CONS(c) and c not in "wxy"

def double_final(h):
    if h in NODOUBLE: return False
    if h in DOUBLE: return True
    return cvc(h) and len(h) <= 4          # short single-syllable CVC

def past_of(h):
    if h in IRREG: return IRREG[h]
    if h.endswith("e"): return h+"d"
    if len(h)>1 and h.endswith("y") and CONS(h[-2]): return h[:-1]+"ied"
    if double_final(h): return h+h[-1]+"ed"
    return h+"ed"

def cont_of(h):
    if h.endswith("ie"): return h[:-2]+"ying"
    if h.endswith("ee") or h.endswith("ye") or h.endswith("oe"): return h+"ing"
    if h.endswith("e"): return h[:-1]+"ing"
    if double_final(h): return h+h[-1]+"ing"
    return h+"ing"

def split_head(word):
    if " " in word: h,r = word.split(" ",1); return h,(" "+r)
    if "-" in word: h,r = word.split("-",1); return h,("-"+r)
    return word,""

# multi-word bases that are NOT action verbs -> never conjugate (head-conjugation makes garbage)
NO_CONJUGATE = set(x.lower() for x in [
 "men-holding-hands","women-holding-hands","bunny-ears","lotus-position","meditation-pose",
 "trial and error","audio call","fist-bumps",
])
# compound verbs where the verb is NOT the first word -> explicit (past, cont) forms
CONJ_OVERRIDE = {
 "bungee-jump": ("bungee-jumped","bungee-jumping"),
 "role-play":   ("role-played","role-playing"),
 "fist-bump":   ("fist-bumped","fist-bumping"),
 "taste-test":  ("taste-tested","taste-testing"),
}

def conj(word, tense):
    if tense=="future": return "will "+word
    ov = CONJ_OVERRIDE.get(word.lower())
    if ov: return ov[0] if tense=="past" else ov[1]
    h,rest = split_head(word)
    return (past_of(h) if tense=="past" else cont_of(h)) + rest

# ---- base-verb detection ----
def parse(fn):
    stem = fn[:-4]
    m = re.search(r'\s\((M|F)\)$', stem)
    g = m.group(1) if m else ""
    w = re.sub(r'\s\((M|F)\)$', '', stem)
    w = re.sub(r'\s\(\d+\)$', '', w).strip()
    return w, g

_meta = re.compile(r'<title\b.*?</title>|<!--.*?-->|<metadata\b.*?</metadata>|\sdata-copyright="[^"]*"', re.S)
_ws = re.compile(r'\s+')
def body_hash(path):
    s = open(path, encoding="utf-8", errors="ignore").read()
    return hashlib.md5(_ws.sub(" ", _meta.sub("", s)).strip().encode()).hexdigest()

def main():
    files = glob.glob(os.path.join(VERBS, "**", "*.svg"), recursive=True)
    words = set(); byfile = []
    for p in files:
        w,g = parse(os.path.basename(p)); words.add(w.lower()); byfile.append((p,w,g))
    ING_BASE = set("sing bring ring cling fling sting swing wing spring string wring".split())
    ED_BASE  = set("feed need speed bleed breed seed weed heed wed embed shed shred sled "
                   "proceed exceed succeed".split())
    IRREG_PAST = set(v for k, v in IRREG.items() if v != k)   # went, slept, spun, swam, ate, ran...
    def is_tense_form(w):
        lw = w.lower()
        if lw.startswith("will "): return True
        head = re.split(r'[ \-]', lw)[0]          # the HEAD word carries the tense
        if head in IRREG_PAST: return True         # irregular PAST forms are tenses, NOT bases to re-conjugate
        if head.endswith("ing") and len(head) > 4 and head not in ING_BASE: return True
        if head.endswith("ed")  and len(head) > 3 and head not in ED_BASE:  return True
        return False

    bases = [(p,w,g) for (p,w,g) in byfile if not is_tense_form(w) and w.lower() not in NO_CONJUGATE]
    mode = "apply" if "--apply" in sys.argv else ("sample" if "--sample" in sys.argv else "dry")
    man = {"created":[], "stamped_inplace":[], "skipped_distinct":[]}
    sample_targets = []
    for p,w,g in bases:
        folder = os.path.dirname(p); suf = f" ({g})" if g else ""
        for tense in ("past","future","cont"):
            name = conj(w, tense) + suf + ".svg"
            tp = os.path.join(folder, name)
            # CRITICAL: never write the target when it IS the base file (e.g. hit->hit, read->read).
            # open(tp,'w') would truncate the base to 0 bytes before annotate() could read it.
            if os.path.abspath(tp) == os.path.abspath(p):
                man.setdefault("skipped_same_as_base", []).append(os.path.relpath(p, VERBS))
                continue
            try:
                out = TA.annotate(p, tense)          # read base + build BEFORE any open(tp,'w')
                if os.path.exists(tp):
                    if body_hash(tp) == body_hash(p):
                        man["stamped_inplace"].append(os.path.relpath(tp, VERBS))
                        if mode=="apply": open(tp,"w").write(out)
                    else:
                        man["skipped_distinct"].append(os.path.relpath(tp, VERBS))
                else:
                    man["created"].append([os.path.relpath(p,VERBS), os.path.relpath(tp,VERBS)])
                    if mode=="apply": open(tp,"w").write(out)
            except Exception as e:
                man.setdefault("failed",[]).append([os.path.relpath(p,VERBS), tense, str(e)])
        if mode=="sample" and len(sample_targets)<8 and g in ("M",""):
            sample_targets.append((p,w,g))

    print(f"verb files: {len(files)} | base verbs (excl tense forms): {len(bases)}")
    print(f"WOULD create: {len(man['created'])} | stamp-in-place(existing copy): {len(man['stamped_inplace'])} | skip(distinct pose): {len(man['skipped_distinct'])}")
    print("\nSAMPLE conjugations:")
    for w in sorted(words)[::max(1,len(words)//40)][:40]:
        print(f"   {w:22s} past={conj(w,'past'):24s} cont={conj(w,'cont'):24s} fut={conj(w,'future')}")
    if mode=="sample":
        OUT="/tmp/tense_s"; os.makedirs(OUT,exist_ok=True)
        picks=["walk","run","eat","jump","apply cream","balance on a beam","swim","write"]
        rendered=[]
        for w in picks:
            src=os.path.join(VERBS,"**",f"{w} (M).svg")
            g=glob.glob(src, recursive=True) or glob.glob(os.path.join(VERBS,"**",f"{w}.svg"),recursive=True)
            if not g: continue
            for t in ("past","cont","future"):
                open(f"{OUT}/{w}-{t}.svg","w").write(TA.annotate(g[0],t)); rendered.append(f"{w}-{t}")
        print("\nsample svgs written to /tmp/tense_s:", rendered)
    if mode=="apply":
        json.dump(man, open("/Users/paulblenkhorn/Desktop/picom_review/tense_manifest.json","w"), indent=0)
        print("APPLIED + manifest saved")

if __name__=="__main__":
    main()
