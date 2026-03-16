from sentence_transformers import SentenceTransformer, util
import torch
import datetime
import regex as re
from rapidfuzz import fuzz
from Processor import TextProcess

# skor anlamları
#   1.00 -> birebir eşleşme
#   0.95 -> diğer ad eşleşmesi
#   0.90 -> token
#   0.85 -> fuzzy 
#   0.55–0.65 -> embedding

tp = TextProcess()

priority_list = {"hard_requirement": 2, "soft_requirement": 1, "bonus": 0} #bir özellik birden fazla geçiyorsa türünü belirlemek için

map_section = {
    "skills":     ["skills", "languages", "certifications"],
    "experience": ["experience", "projects"],
    "education":  ["education"],
    "summary":    ["summary"],
}

map_threshold = {"hard_requirement": 0.65, "soft_requirement": 0.55, "bonus": 0.50, "personal_trait": 0.45, "education": 0.65}


class EmbeddingCVMatcher:
    def __init__(self, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = SentenceTransformer(model_name)

    def score_cv(self, clean_sections, requirements, threshold=0.55, personal_trait_mode="search"):
        """
        returns
            overall_score
            details
            logistics_notes : skorlamaya dahil edilmeyen özellikler
        """
        
        cv_full = " ".join([clean_sections.get(a, "") for a in ["experience", "projects", "education"]])
        cv_text = tp.split_sentence(cv_full)

        skills_raw = clean_sections.get("skills", "")
        if isinstance(skills_raw, str):
            skills_list = []
            for s in skills_raw.split("\n"):
                clean = s.strip()
                if clean:
                    skills_list.append(clean)
        else:
            skills_list = skills_raw
                
        skills_embedding = self.model.encode(skills_list, convert_to_tensor=True) if skills_list else None
        cv_text.extend(skills_list)

        if not cv_text:
            print("--HATA: cvden metin gelmedi")
            return {"total_score": 0, "matches": []}

        # fazla skilleri birleştirme
        birles = {}
        for req in requirements:
            key = "||".join([req.get("skill_en", ""), req.get("skill_tr", ""), req.get("type", ""), req.get("degree_level", "")])
            if key not in birles:
                birles[key] = dict(req)
            else:
                mevcut = birles[key]
                mevcut["weight"]    = max(mevcut.get("weight", 0),      req.get("weight", 0))
                mevcut["min_years"] = max(mevcut.get("min_years") or 0, req.get("min_years") or 0)
                if priority_list.get(req.get("priority", "bonus"), 0) > priority_list.get(mevcut.get("priority", "bonus"), 0):
                    mevcut["priority"] = req["priority"]
        requirements = list(birles.values())



        result = []
        skor = 0
        max_weight = 0
        logistics_notes = []
        seen = set()

        for req in requirements:
            # skoru hesaplanmayanlar
            if req.get("type") == "logistics":
                logistics_notes.append({
                    "note":     f"{req.get('skill_tr', '')} ({req.get('skill_en', '')})",
                    "priority": req.get("priority", "")
                })
                continue

            # --eğitim
            if req.get("type") == "education":
                is_matched = False
                best_score = 0
                point = 0

                for cv_edu in clean_sections.get("education_structured", []):
                    skill_en = req.get("skill_en", "")
                    skill_tr = req.get("skill_tr", "")
                    
                    skills = f"{skill_en} {skill_tr}"
                    skills = skills.lower()
                    split_parts = re.split(r",|veya|or", skills)


                    req_fields = []
                    for part in split_parts:
                        cleaned_part = part.strip()
                        if cleaned_part:
                            req_fields.append(cleaned_part)


                    degree_raw = cv_edu.get('degree')
                    if not degree_raw:
                        degree_raw = ""
                        
                    university_raw = cv_edu.get('university')
                    if not university_raw:
                        university_raw = ""
                        
                    combined_name = f"{degree_raw} {university_raw}"
                    cv_name = combined_name.lower()

                    # substring sonra embed
                    field_match = any(x in cv_name or cv_name in x for x in req_fields)
                    if not field_match and cv_name.strip():
                        req_emb = self.model.encode(f"{skill_en} {skill_tr}".strip(), convert_to_tensor=True)
                        cv_emb  = self.model.encode(cv_name, convert_to_tensor=True)
                        field_match = util.cos_sim(req_emb, cv_emb)[0][0].item() > map_threshold["education"]

                    degree_match = req.get("degree_level", "belirtilmemiş") in (cv_edu.get("degree_type"), "belirtilmemiş")
                    status_match = req.get("degree_status", "fark etmez") in (cv_edu.get("degree_status"), "fark etmez")

                    if field_match and degree_match and status_match:
                        is_matched = True
                        best_score = 1.0
                        point = req["weight"]
                        break

                skor += point
                max_weight += req["weight"]
                result.append({
                    "skill":       f"{req.get('skill_tr', req.get('skill_en', ''))} (education)",
                    "match_score": best_score,
                    "years_found": 0,
                    "is_matched":  is_matched,
                    "weight":      req["weight"]
                })
                print(f"{'O' if is_matched else 'X'} - Education: {req.get('skill_en')} / {req.get('skill_tr')} ({req.get('degree_level')} - {req.get('degree_status')}) Weight: {req['weight']}")
                continue

            # --kişisel özellikler
            if req.get("type") == "personal_trait" and personal_trait_mode == "ignore":
                continue

            req_text = f"{req.get('skill_en', '')} {req.get('skill_tr', '')}".strip()
            if req_text in seen:
                continue
            seen.add(req_text)

            # diğer adları ekle
            aliases     = [tp.turkish_lower(a).strip() for a in req.get("aliases", []) if a.strip()]
            match_terms = list(filter(None, [tp.turkish_lower(req.get("skill_en", "")), tp.turkish_lower(req.get("skill_tr", ""))] + aliases))

            # aranacak bölümler
            if req.get("type") == "personal_trait":
                search_sections = ["skills", "summary", "languages", "certifications"]
            else:
                target = req.get("target_section", "experience")
                search_sections = map_section.get(target, ["experience", "projects"])

            if req.get("priority") == "soft_requirement" and "summary" not in search_sections:
                search_sections = search_sections + ["summary"]

            req_threshold = map_threshold.get(req.get("priority") if req.get("type") != "personal_trait" else "personal_trait", threshold)
            section_text = " ".join([clean_sections.get(s, "") for s in search_sections])
            section_chunks = tp.split_sentence(section_text)
            if "skills" in search_sections:
                section_chunks.extend(skills_list)
            section_embedding = self.model.encode(section_chunks, convert_to_tensor=True) if section_chunks else None

            all_cv_text_norm = tp.turkish_lower(" ".join([str(v) for v in clean_sections.values() if isinstance(v, str)]))
            req_embedding    = self.model.encode(f"{req.get('skill_en', '')} {req.get('skill_tr', '')} {' '.join(req.get('aliases', []))}".strip(), convert_to_tensor=True)

            best_score = 0.0
            is_matched = False
            found_word = ""

            # tam eşleşme
            for term in match_terms:
                pattern = rf"\b{re.escape(term)}\b" if len(term) <= 3 else None
                if (pattern and re.search(pattern, all_cv_text_norm)) or (not pattern and term in all_cv_text_norm):
                    best_score = 0.95
                    is_matched = True
                    found_word = term
                    break

            # fuzzy eşleşme
            if not is_matched:
                for term in match_terms:
                    if len(term) <= 4:
                        continue
                    term_wc = len(term.split())
                    for sentence in cv_text:
                        words = tp.turkish_lower(sentence).split()

                        # sliding window (iyi sonuç verdi)
                        for i in range(len(words) - term_wc + 1):
                            ngram = " ".join(words[i:i + term_wc])
                            if fuzz.ratio(term, ngram) >= 85:
                                best_score = 0.85
                                is_matched = True
                                found_word = ngram
                                break
                            
                        # ocr'yi biraz temizlemeye çalışıyor
                        if not is_matched and term_wc > 1:
                            combined = term.replace(" ", "")
                            for word in words:
                                if fuzz.ratio(combined, word) >= 85:
                                    best_score = 0.85
                                    is_matched = True
                                    found_word = word
                                    break
                        if is_matched:
                            break
                    if is_matched:
                        break

            # token
            if not is_matched:
                for skill in skills_list:
                    skill_tokens = set(tp.turkish_lower(skill).split())
                    for term in match_terms:
                        term_tokens = set(term.split())
                        if term_tokens and len(term_tokens & skill_tokens) / len(term_tokens) >= 0.70: # %70 benzerlik
                            best_score = 0.90
                            is_matched = True
                            found_word = skill
                            break
                    if is_matched:
                        break

            # embed
            if not is_matched and skills_embedding is not None:
                skill_scores = util.cos_sim(req_embedding, skills_embedding)[0]
                top_k        = min(3, len(skill_scores))
                top_scores, _ = torch.topk(skill_scores, top_k)
                skill_best   = top_scores[0].item()
                skill_mean   = top_scores.mean().item()

                if skill_best >= 0.65:
                    best_score = skill_best
                    is_matched = True
                elif skill_best >= req_threshold:
                    best_score = skill_mean
                    is_matched = True

                    if section_embedding is not None:
                        cv_scores = util.cos_sim(req_embedding, section_embedding)[0]
                        cv_mean   = torch.topk(cv_scores, min(3, len(cv_scores))).values.mean().item()
                        if cv_mean > best_score:
                            best_score = cv_mean

            # embed
            if not is_matched and section_embedding is not None:
                cv_scores  = util.cos_sim(req_embedding, section_embedding)[0]
                top_k      = min(3, len(cv_scores))
                top_scores, _ = torch.topk(cv_scores, top_k)
                best_score = top_scores.mean().item()
                is_matched = best_score >= req_threshold

            is_matched = best_score >= req_threshold

            # yıl hesaplama
            point   = 0
            cv_year = None

            if is_matched:
                for skill_name, years in clean_sections.get("skill_years", {}).items():
                    if tp.turkish_lower(req.get("skill_en", "")) in tp.turkish_lower(skill_name) or \
                       tp.turkish_lower(req.get("skill_tr", "")) in tp.turkish_lower(skill_name):
                        cv_year = years
                        break

                required_years = req.get("min_years", 0)
                if required_years > 0:
                    point = req["weight"] * min(1.5, cv_year / required_years) if cv_year else req["weight"]
                else:
                    point = req["weight"]
                if cv_year is None:
                    cv_year = 0

            skor      += point
            max_weight += req["weight"]

            result.append({
                "skill":       f"{req['skill_tr']} ({req['skill_en']})",
                "match_score": round(best_score, 2),
                "years_found": cv_year if is_matched else 0,
                "is_matched":  is_matched,
                "weight":      req["weight"]
            })
            found_info = f", found: '{found_word}'" if is_matched else ""
            print(f"{'O' if is_matched else 'X'} - Skill: {req['skill_tr']}, Score: {best_score:.3f}, Weight: {req['weight']}, Type: {req['type']}{found_info}")

        final_percentage = (skor / max_weight * 100) if max_weight > 0 else 0
        return {
            "overall_score":  round(final_percentage, 2),
            "details":        result,
            "logistics_notes": logistics_notes
        }