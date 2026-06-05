import os
import yaml
from difflib import SequenceMatcher

PROJECT_ROOT = "/home/onegem/work/steel-qto"
config_path = os.path.join(PROJECT_ROOT, "config", "dedup_routing.yaml")
final_output_path = os.path.join(PROJECT_ROOT, "outputs", "llm_experiments", "dedup_routing.yaml")

def calculate_semantic_similarity(dict_correct, dict_predicted):
    if not isinstance(dict_correct, dict) or not isinstance(dict_predicted, dict):
        return 0.0, 0, 0
    
    total_fields = 0
    matched_fields = 0
    
    def compare_dicts(d1, d2):
        nonlocal total_fields, matched_fields
        if not isinstance(d1, dict) or not isinstance(d2, dict):
            return
        for k, v in d1.items():
            if k in ("count_from", "spec_from", "count_override", "skip", "skip_reason"):
                total_fields += 1
                v_clean = str(v).strip().replace(" ", "").replace("(", "").replace(")", "").replace("_", "").replace("-", "") if v is not None else ""
                
                v2 = d2.get(k)
                v2_clean = str(v2).strip().replace(" ", "").replace("(", "").replace(")", "").replace("_", "").replace("-", "") if v2 is not None else ""
                
                if v_clean == v2_clean:
                    matched_fields += 1
            elif isinstance(v, dict):
                if k in d2 and isinstance(d2[k], dict):
                    compare_dicts(v, d2[k])
                    
    compare_dicts(dict_correct, dict_predicted)
    pct = (matched_fields / total_fields * 100) if total_fields > 0 else 100.0
    return pct, matched_fields, total_fields

if not os.path.exists(config_path):
    print("❌ 정답지(config/dedup_routing.yaml)가 존재하지 않습니다.")
    exit(1)

if not os.path.exists(final_output_path):
    print("❌ 최종 출력본(outputs/llm_experiments/dedup_routing.yaml)이 존재하지 않습니다.")
    exit(1)

with open(config_path, "r", encoding="utf-8") as f:
    correct_data = yaml.safe_load(f) or {}

with open(final_output_path, "r", encoding="utf-8") as f:
    predicted_data = yaml.safe_load(f) or {}

print("📊 [실시간 대조] 최종 dedup_routing.yaml 출력본 vs 기존 config/dedup_routing.yaml 정답지 비교")
print("=" * 80)

for drawing_name in ["도면1", "도면2", "도면3", "도면4", "도면5"]:
    dict_correct = correct_data.get(drawing_name, {})
    dict_predicted = predicted_data.get(drawing_name, {})
    
    # 1) 대안 A (바이트) 일치율: 정렬을 정규화한 YAML 문자열 덤프 기준 비교
    correct_raw_dump = yaml.dump(dict_correct, allow_unicode=True, default_flow_style=False, sort_keys=True)
    predicted_raw_dump = yaml.dump(dict_predicted, allow_unicode=True, default_flow_style=False, sort_keys=True)
    byte_ratio = SequenceMatcher(None, correct_raw_dump, predicted_raw_dump).ratio() * 100
    
    # 2) 대안 B (의미론적) 일치율: 실제 키-값 매핑 값 비교
    semantic_ratio, matched, total = calculate_semantic_similarity(dict_correct, dict_predicted)
    
    print(f"📍 {drawing_name}:")
    print(f"   - 대안 A (바이트) 일치율     : {byte_ratio:.2f}% (키 정렬 순서를 맞추었으나 미세 줄바꿈/공백 차이 반영)")
    print(f"   - 대안 B (의미론적) 일치율   : {semantic_ratio:.1f}% ({matched}/{total}개 매핑 항목 일치)")
    print("-" * 80)
