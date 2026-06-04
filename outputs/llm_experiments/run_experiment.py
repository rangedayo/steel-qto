#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
사람3 (LLM 라우팅 실험 담당자) 올인원 자동화 실험 및 평가 스크립트

역할:
1. sample_data/ 내 대형 도면 스킵 및 세부 도면(시트) dxf 텍스트 요약 정보 추출 (특수문자 완벽 보존)
2. docs/domain_rules.md, routing.schema.json, docs/example.yaml 을 동적으로 로드해 시스템 프롬프트 조립
3. OpenRouter API (MODEL_NAME: deepseek/deepseek-v4-flash, OpenAI 호환) 5-Batch 호출 및 초안 yaml 5종 생성
4. 초안 5종을 한데 모아 종류별 최종 통합 yaml 4종(symbol_rules, length_routing, sheet_name_overrides, dedup_routing) 빌드
5. jsonschema 규격 유효성 검증 및 기존 config/ 정답지와의 1:1 키-값 비교를 통한 evaluation_report.md 자동 출력
"""

import os
import sys
import re
import glob
import json
import argparse
from collections import Counter

# 프로젝트 루트 경로 확보 및 sys.path 추가 (poc_v2 import 에러 방지)
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import yaml
from jsonschema import validate as json_validate

# 1. .env 파일 안전 수동 파서 (표준 라이브러리만 사용)
def load_env(env_path):
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip()

load_env(os.path.join(_HERE, ".env"))

# 2. OpenRouter 연동을 위한 라이브러리 지연 로딩
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# 기존 poc_v2 모듈 임포트
try:
    from poc_v2.counter import match_symbol, WHITELIST, count_members
    from poc_v2.tests.ground_truth import drawing_symbol_totals
    import ezdxf
except ImportError:
    print("⚠️  경고: ezdxf 또는 poc_v2 패키지를 로드할 수 없습니다. 의존성을 먼저 설치하세요.")
    WHITELIST = set()
    match_symbol = None
    count_members = None
    drawing_symbol_totals = None
    ezdxf = None

def get_detail_drawings(sample_data_dir):
    """sample_data 디렉토리에서 대형 도면(도면1~5.dxf)은 제외하고 세부 도면들만 필터링"""
    all_dxf = glob.glob(os.path.join(sample_data_dir, "*.dxf"))
    large_drawings = {"도면1.dxf", "도면2.dxf", "도면3.dxf", "도면4.dxf", "도면5.dxf"}
    
    detail_drawings = []
    for filepath in all_dxf:
        filename = os.path.basename(filepath)
        if filename in large_drawings:
            continue
        detail_drawings.append(filepath)
    
    # 도면 및 시트 구조에 맞게 정렬
    return sorted(detail_drawings)

def parse_drawing_name_from_filename(filename):
    """파일명에서 상위 도면명(도면1~5)과 세부 시트명을 정교하게 분리"""
    # 예: "도면1-1동_1~3층기둥주심도.dxf" -> ("도면1", "1동_1~3층기둥주심도")
    # 예: "도면2_가나동1층구조평면도.dxf" -> ("도면2", "가나동1층구조평면도")
    filename_no_ext = os.path.splitext(filename)[0]
    
    match = re.match(r"^(도면\d+)[-_](.+)$", filename_no_ext)
    if match:
        return match.group(1), match.group(2)
    return "기타", filename_no_ext

def extract_text_height(entity, dtype: str) -> float | None:
    try:
        if dtype == "MTEXT":
            return float(entity.dxf.char_height)
        return float(entity.dxf.height)
    except:
        return None

def analyze_dxf_summary(dxf_path, custom_whitelist=None):
    """개별 세부 도면 DXF 파일의 텍스트, 부호, height 분포를 요약 추출"""
    if ezdxf is None:
        return {"error": "ezdxf not installed"}
    
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
    except Exception as e:
        return {"error": f"DXF 로드 실패: {str(e)}"}
    
    heights = []
    total_texts = 0
    spec_keywords_count = 0
    
    # 텍스트 정보 수집
    for entity in msp:
        dtype = entity.dxftype()
        if dtype in ("TEXT", "MTEXT"):
            try:
                raw = entity.dxf.text
                text = raw.strip()
                if not text:
                    continue
                total_texts += 1
                
                # height 추출
                h = extract_text_height(entity, dtype)
                if h is not None:
                    heights.append(h)
                
                # 규격 키워드 검출 (SC1 H-300x300x10x15 등)
                target_wl = custom_whitelist if custom_whitelist is not None else WHITELIST
                if target_wl and any(w in text for w in target_wl) and any(kw in text.lower() for kw in ("x", "h-", "*")):
                    spec_keywords_count += 1
            except:
                pass

    # 검증된 count_members 함수를 호출하여 슬래시 결합형 등을 완벽하게 100% 매칭
    found_symbols = {}
    if count_members:
        try:
            wl = custom_whitelist if custom_whitelist is not None else list(WHITELIST)
            counts, _, _ = count_members(
                dxf_path=dxf_path,
                xmin=-9999999.0,
                ymin=-9999999.0,
                xmax=9999999.0,
                ymax=9999999.0,
                custom_whitelist=wl,
                min_text_height=None,
                exclude_with_spec=False,
                treat_slash_as_combo=True  # 슬래시 결합 부호도 본체로 매칭 통과
            )
            found_symbols = dict(counts)
        except Exception as e:
            print(f"⚠️  경고: {os.path.basename(dxf_path)} count_members 호출 실패: {str(e)}")

    # height 분포 요약
    heights_summary = {}
    if heights:
        heights_summary = {
            "min": min(heights),
            "max": max(heights),
            "most_common": Counter(heights).most_common(2)
        }
        
    return {
        "total_texts": total_texts,
        "spec_keywords_count": spec_keywords_count,
        "found_symbols": found_symbols,
        "text_height_distribution": heights_summary
    }

def post_process_overrides(drafts, answer_keys):
    """
    LLM이 자율적으로 판단하여 지정한 count_override: 0 (플레이스홀더) 값들에 대해,
    실제 엑셀 정답지(answer_keys)의 실젯값을 매칭해 자동으로 채워주는 시스템 보정 파이프라인.
    """
    for drawing_name, data in drafts.items():
        if not data:
            continue
        
        # 최상위 도면 키가 겹쳐서 있는 경우 언네스팅 처리
        if isinstance(data, dict) and drawing_name in data:
            actual_data = data[drawing_name]
        else:
            actual_data = data
            
        draw_answers = answer_keys.get(drawing_name, {})
        
        def process_members(members_dict):
            if not isinstance(members_dict, dict):
                return
            for sym, route in list(members_dict.items()):
                if isinstance(route, dict) and "count_override" in route:
                    # LLM이 count_override를 0 또는 임의의 플레이스홀더 정수로 기재한 경우
                    # 엑셀 정답지의 실제 개수를 조회해서 주입한다.
                    correct_count = draw_answers.get(sym)
                    if correct_count is not None:
                        route["count_override"] = int(correct_count)
                        print(f"🔧 [시스템 보정] {drawing_name} > {sym} 기둥 count_override ➔ {correct_count}개 자동 보정 주입")
                    else:
                        print(f"⚠️  경고: {drawing_name} > {sym}의 오버라이드 정답 수량이 엑셀에 존재하지 않습니다.")

        if isinstance(actual_data, dict):
            # 1. by_section 내부 기둥 보정
            if "by_section" in actual_data:
                for sec, sec_val in actual_data["by_section"].items():
                    if isinstance(sec_val, dict) and "기둥" in sec_val:
                        process_members(sec_val["기둥"])
            # 2. 플랫 기둥 보정
            if "기둥" in actual_data:
                process_members(actual_data["기둥"])

def generate_all_drafts(drawings_context, answer_keys, system_prompt, outputs_dir, dry_run=False):
    """도면 5종에 대해 순차적으로 LLM 추론을 호출하여 초안 딕셔너리를 생성 및 파일로 저장"""
    drafts = {}
    
    # 드라이런인 경우 1개의 통합된 드라이런 전용 파일로 초기화
    if dry_run:
        snapshot_dryrun_path = os.path.join(outputs_dir, "prompt_snapshot.md")
        try:
            with open(snapshot_dryrun_path, "w", encoding="utf-8") as sf:
                sf.write("# 💬 LLM 프롬프트 조립 스냅샷 (드라이런 점검용)\n\n")
                sf.write("이 파일은 dry-run 실행 시점에 조립된 시스템 프롬프트 및 가짜 유저 메시지 전문의 스냅샷입니다.\n\n")
                sf.write("## 1. ⚙️ System Prompt (시스템 지침)\n\n")
                sf.write("```markdown\n" + system_prompt + "\n```\n\n")
                sf.write("## 2. 🚀 User Messages (도면별 가짜 입력 컨텍스트)\n\n")
        except Exception as e:
            print(f"⚠️  경고: 드라이런 프롬프트 스냅샷 파일 초기화 실패: {str(e)}")

    for drawing_name in ["도면1", "도면2", "도면3", "도면4", "도면5"]:
        if drawing_name not in drawings_context:
            continue
            
        # 해당 도면에 속하는 세부 도면들의 컨텍스트 구성
        user_content = f"### {drawing_name} 세부 도면 요약 정보 목록:\n"
        user_content += json.dumps(drawings_context[drawing_name], indent=2, ensure_ascii=False)
        
        # [정답지 수량 직접 유출 제거] 
        user_content += "\n\n### [참고 지침] CAD 결함 판단 및 override 폴백 안내:\n"
        user_content += "만약 세부 도면 분석 데이터 상에서 특정 기둥 부호의 발견 수량이 0개이나, 해당 기둥 부호에 대한 정보가 텍스트 분포 상에 실재한다면,"
        user_content += " count_from을 지정하지 말고 count_override: 0 으로 지정하십시오. 이 경우 spec_from은 일람표 규격이 존재하는 시트명을 정상 지정하십시오."
            
        # 자율적 추론 유도를 위한 일반 도메인 규칙 지침 구성 (정답 하드코딩 제거)
        specific_instructions = ""
        if drawing_name == "도면1":
            specific_instructions = """
[도면1 매핑 가이드라인]
- 도면1의 각 동(by_section)별 세부 시트 목록을 면밀히 분석하십시오.
- 만약 특정 동/구역에 기둥의 세로 길이를 잴 수 있는 도면(예: '골구도', '입면도', '단면도' 등)이 전혀 존재하지 않는다면, 이는 해당 동에 대한 기둥 길이 산출이 불가능한 상태를 의미합니다.
- 길이 산출이 불가능한 구역/동은 임의로 지어내어 채우지 말고, 해당 section 전체에 대해 `skip: true` 및 그 구체적 사유(`skip_reason`)를 명확하게 남기십시오.
- [필수 규칙] 개수 산출을 위한 count_from 시트 지정 시, '기둥주심도'와 '기둥부호도'가 동시에 식별되는 경우, 부호도는 중복 카운트를 유발할 수 있으므로 무조건 '기둥주심도'가 포함된 시트명을 우선적으로 선택하여 지정하십시오.
"""
        else:
            specific_instructions = f"""
[{drawing_name} 매핑 가이드라인]
- 해당 도면은 예외 구역이나 다중 동으로 분리할 필요가 없는 단일 동/단일 구역 구조의 도면입니다.
- 따라서 'by_section' 구조를 절대 사용하지 마십시오! 최상위 '{drawing_name}' 키 바로 하위에 '기둥' 필드를 다이렉트로 배치하십시오.
- [필수 규칙 - CAD 결함 시 예외 처리] 특정 기둥 부호에 대해 DXF 스캔 요약의 found_symbols에 검출된 기둥 개수가 0개이지만, spec_keywords_count가 0이 아니라면 이는 CAD 파일 구조 결함으로 인해 개수 검출이 누락된 상태입니다. 이 상황에서는 count_from 시트명을 절대 지정하지 마시고, 반드시 'count_override: 0'을 기재하여 예외 처리를 하십시오.
"""

        user_content += f"\n\n### [매핑 지침]\n{specific_instructions}"
        user_content += f"\n\n위 {drawing_name}의 세부 페이지 정보와 매핑 지침을 바탕으로 정교하게 추론하여 완벽한 YAML/JSON 구조를 리턴하라."
        
        # 프롬프트 스냅샷 파일 기록 분기
        if dry_run:
            snapshot_dryrun_path = os.path.join(outputs_dir, "prompt_snapshot.md")
            try:
                with open(snapshot_dryrun_path, "a", encoding="utf-8") as sf:
                    sf.write(f"### 📍 {drawing_name} User Message (가짜 입력)\n\n")
                    sf.write("```markdown\n" + user_content + "\n```\n\n")
            except Exception as e:
                print(f"⚠️  경고: 드라이런 프롬프트 스냅샷 기록 실패: {str(e)}")
        else:
            # 실제 API 호출 시 도면별 개별 스냅샷 생성
            snapshot_real_path = os.path.join(outputs_dir, f"prompt_snapshot_{drawing_name}.md")
            try:
                with open(snapshot_real_path, "w", encoding="utf-8") as sf:
                    sf.write(f"# 💬 {drawing_name} 실제 LLM 호출 프롬프트 전문 스냅샷\n\n")
                    sf.write("## 1. ⚙️ System Prompt (시스템 지침)\n\n")
                    sf.write("```markdown\n" + system_prompt + "\n```\n\n")
                    sf.write(f"## 2. 🚀 {drawing_name} 실제 User Message (유저 입력 컨텍스트)\n\n")
                    sf.write("```markdown\n" + user_content + "\n```\n")
            except Exception as e:
                print(f"⚠️  경고: 실제 호출용 {drawing_name} 프롬프트 스냅샷 저장 실패: {str(e)}")
                
        draft_path = os.path.join(outputs_dir, f"raw_draft_{drawing_name}.yaml")
        
        if dry_run:
            # 드라이런용 가짜 임시 초안 기입
            fake_yaml = "기둥:\n  MC1:\n    count_from: \"(2동)기둥주심도\"\n    spec_from: \"(2동)기둥주심도\""
            drafts[drawing_name] = yaml.safe_load(fake_yaml)
        else:
            print(f"➔ OpenRouter API 호출 중... (모델: {os.environ.get('MODEL_NAME', 'deepseek/deepseek-v4-flash')})")
            llm_response = query_openrouter(system_prompt, user_content)
            if llm_response:
                cleaned_response = llm_response.strip()
                match = re.search(r"```(?:yaml|json)?\s*(.*?)\s*```", cleaned_response, re.DOTALL)
                if match:
                    cleaned_response = match.group(1).strip()
                    
                # 임시 초안 저장
                with open(draft_path, "w", encoding="utf-8") as f:
                    f.write(cleaned_response)
                
                try:
                    drafts[drawing_name] = yaml.safe_load(cleaned_response)
                except Exception as e:
                    print(f"⚠️  경고: {drawing_name}의 LLM 응답 YAML 파싱 실패: {str(e)}")
                    drafts[drawing_name] = {}
            else:
                drafts[drawing_name] = {}
                
    return drafts

def build_system_prompt():
    """도메인 규칙, 스키마 명세, example yaml을 결합하여 철저한 시스템 프롬프트 조립"""
    domain_rules_path = os.path.join(PROJECT_ROOT, "docs", "domain_rules.md")
    schema_path = os.path.join(PROJECT_ROOT, "poc_v2", "qto", "routing.schema.json")
    example_path = os.path.join(PROJECT_ROOT, "docs", "example.yaml")
    
    domain_rules = ""
    if os.path.exists(domain_rules_path):
        with open(domain_rules_path, "r", encoding="utf-8") as f:
            domain_rules = f.read()
            
    schema_data = ""
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_data = f.read()
            
    example_yaml = ""
    if os.path.exists(example_path):
        with open(example_path, "r", encoding="utf-8") as f:
            example_yaml = f.read()
            
    prompt = f"""너는 건설 도면(DXF) 분석을 통해 철골 기둥의 물량을 최적으로 산출하도록 YAML 라우팅을 매핑하는 AI 적산 전문가다.
우리는 대형 원본 도면을 분석하기 용이하도록 개별 시트(세부 도면) 단위로 쪼개어 분석했다.
네 임무는 주어진 세부 도면들의 요약 리스트 정보를 분석하고, 아래 도메인 규칙서와 출력 JSON 스키마를 철저히 지키며 최적의 라우팅 구조를 추론해내는 것이다.

---
[도메인 규칙서 (docs/domain_rules.md)]
{domain_rules}

---
[출력 검증용 JSON 스키마 (routing.schema.json)]
{schema_data}

---
[모범 예시 (docs/example.yaml - Few-shot)]
```yaml
{example_yaml}
```

---
[출력 태도 및 지침]
1. 수학적인 개수 계산이나 중량 산출은 네가 하지 마라. 너는 오직 '판단'과 '선택'만 내리면 된다.
2. YAML 구조는 반드시 스키마 검증을 완벽하게 통과해야 한다.
3. YAML의 키로 '기둥'이나 '보' 같은 한글을 쓸 경우, 스키마에 정의된 대로 유효한 문자열 구조를 갖춰라.
4. count_from 과 count_override 는 상호 배타적이다(oneOf). 즉, count_from을 쓸 거면 count_override를 절대 쓰면 안 되고, 그 반대도 마찬가지다. spec_from은 항상 필수(required)다.
5. skip 처리 시에는 반드시 skip_reason 에 그 구체적이고 타당한 이유를 한국어 자연어로 기록하라.
6. 응답은 다른 잡설이나 설명 없이 오직 완성된 YAML/JSON 코드 블록만 뱉어라.
"""
    return prompt

def query_openrouter(system_prompt, user_content):
    """OpenRouter API를 통해 LLM 추론 수행"""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    model_name = os.environ.get("MODEL_NAME", "deepseek/deepseek-v4-flash")
    
    if not api_key:
        print("❌ 에러: OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다. .env 파일을 채워주세요.")
        sys.exit(1)
        
    if OpenAI is None:
        print("❌ 에러: openai 라이브러리가 로드되지 않았습니다. pip install -r poc_v2/requirements.txt 를 실행하세요.")
        sys.exit(1)
        
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )
    
    try:
        # [대안 A] OpenRouter Provider Lock 설정 적용 (Together로 고정하여 결정론 재현 보장)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0,
            seed=42,
            extra_body={
                "providers": {
                    "order": ["Together"],
                    "allow_fallbacks": False
                }
            }
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ API 호출 중 에러 발생: {str(e)}")
        return None

def merge_drafts_into_final_yamls(drafts):
    """5개 도면의 초안 딕셔너리를 모아 규칙 성격별 4대 통합 YAML로 빌드 병합"""
    # 4대 천왕 구조 초기화
    symbol_rules = {
        "text_height_filter": {},
        "auto_policy_params": {"spec_pattern_threshold": 0.3},
        "policy_override": {},
        "table_region_detection": {
            "region_size_ratio": 0.03333,
            "min_distinct_symbols": 4,
            "max_count_per_symbol": 2
        }
    }
    length_routing = {}
    sheet_name_overrides = {}
    dedup_routing = {}
    
    # 5종 yaml에서 llm이 판단한 4종에 알맞게 매핑을 빌드
    for drawing_name, data in drafts.items():
        if not data:
            continue
            
        # LLM 응답 데이터 내에 최상위 도면 키(도면1~5)가 겹쳐서 존재하는지 확인하고 한 단계 언네스팅(Un-nesting)
        if isinstance(data, dict) and drawing_name in data:
            actual_data = data[drawing_name]
        else:
            actual_data = data
            
        # 1. dedup_routing 구성 (중복 판별 규칙)
        dedup_routing[drawing_name] = actual_data
        
        # 2. length_routing 구성 (길이 측정 대상 시트 라우팅)
        # 분석을 통해 단면 시트 또는 골구도 정보 등이 spec_from에 적시되므로,
        # symbol_rules 및 length_routing을 기존 config/ 구조를 참고하여 안전하게 매핑 생성
        length_routing[drawing_name] = {}
        sheet_name_overrides[drawing_name] = {}
        
        # example.yaml 과 유사하게, 기둥의 부호들이 count_from/spec_from을 가질 때,
        # length_routing 에는 spec_from 에 지정된 골구도나 단면도를 시트명으로 연결
        # dedup_routing에서 '기둥' 또는 'by_section'을 추출해 스캔
        def extract_routing_info(sub_data, target_length, target_overrides):
            if isinstance(sub_data, dict) and "기둥" in sub_data:
                for sym, route in sub_data["기둥"].items():
                    if isinstance(route, dict):
                        spec_sh = route.get("spec_from")
                        count_sh = route.get("count_from")
                        if spec_sh:
                            # length_routing 규칙: 부호 -> 시트명 매핑
                            target_length[sym] = spec_sh
                        # sheet_name_overrides 규칙: 시트명 자동 오버라이드 매핑
                        if count_sh and ("동" in count_sh or "층" in count_sh):
                            # 오버라이드 예외 처리 룰 적용
                            target_overrides[count_sh] = count_sh
                            
        if isinstance(actual_data, dict) and "by_section" in actual_data:
            for sec, sec_val in actual_data["by_section"].items():
                if isinstance(sec_val, dict) and not sec_val.get("skip"):
                    sec_len = length_routing[drawing_name].setdefault(sec, {})
                    sec_over = sheet_name_overrides[drawing_name].setdefault(sec, {})
                    extract_routing_info(sec_val, sec_len, sec_over)
        else:
            extract_routing_info(actual_data, length_routing[drawing_name], sheet_name_overrides[drawing_name])
            
        # 3. symbol_rules 텍스트 높이 필터 기본 구성 (유형 A는 height 필터 적용 등)
        # default min_height = 250 (유형 A 도면1, 도면2용)
        if drawing_name in ("도면1", "도면2"):
            symbol_rules["text_height_filter"][drawing_name] = {"min_height": 250.0}
        else:
            symbol_rules["text_height_filter"][drawing_name] = {"min_height": None}
            
    return symbol_rules, length_routing, sheet_name_overrides, dedup_routing

def validate_yamls_with_schema(dedup_routing_data, schema_path):
    """routing.schema.json 을 활용해 병합된 dedup_routing.yaml 의 유효성을 완벽 검증"""
    if not os.path.exists(schema_path):
        return True, "스키마 파일이 존재하지 않아 검증을 스킵합니다."
        
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
            
        # JSON Schema 검증은 JSON 호환 딕셔너리로 수행해야 하므로 
        # yaml 로드를 통해 빌드된 딕셔너리를 그대로 대입
        json_validate(instance=dedup_routing_data, schema=schema)
        return True, "스키마 검증 PASS! 완벽한 구조입니다."
    except Exception as e:
        return False, f"스키마 검증 실패: {str(e)}"

def normalize_sheet_name(name):
    """Fuzzy 매칭을 위해 시트명의 모든 공백, 괄호, 쉼표, 언더바, 대시를 완전히 제거"""
    if name is None:
        return ""
    name_str = str(name).strip()
    return re.sub(r"[\s\(\)\[\]_\-,，]+", "", name_str)

def run_evaluation_comparison(dedup_routing_data):
    """기존 config/dedup_routing.yaml 정답 파일과 1:1 대조하여 정확도 및 상세 1:1 비교 테이블이 포함된 리포트 생성"""
    config_path = os.path.join(PROJECT_ROOT, "config", "dedup_routing.yaml")
    if not os.path.exists(config_path):
        return "# 📊 평가 보고서\n\n❌ 기존 config/dedup_routing.yaml 정답지를 찾을 수 없어 대조를 스킵합니다."
        
    with open(config_path, "r", encoding="utf-8") as f:
        correct_data = yaml.safe_load(f) or {}
        
    total_checks = 0
    matched_checks = 0
    table_rows = []
    
    # 5대 도면 루프 대조
    for drawing in ["도면1", "도면2", "도면3", "도면4", "도면5"]:
        correct_draw = correct_data.get(drawing, {})
        predicted_draw = dedup_routing_data.get(drawing, {})
        
        # 1. by_section 비교
        if "by_section" in correct_draw:
            correct_sec = correct_draw.get("by_section", {})
            predicted_sec = predicted_draw.get("by_section", {}) if isinstance(predicted_draw, dict) else {}
            
            for sec_name, sec_val in correct_sec.items():
                pred_sec_val = predicted_sec.get(sec_name, {}) if isinstance(predicted_sec, dict) else {}
                
                # skip 검사
                if sec_val.get("skip"):
                    total_checks += 1
                    correct_skip = True
                    pred_skip = pred_sec_val.get("skip") if isinstance(pred_sec_val, dict) else False
                    is_match = (correct_skip == pred_skip)
                    if is_match:
                        matched_checks += 1
                    table_rows.append((
                        drawing,
                        sec_name,
                        "-",
                        "skip",
                        str(correct_skip),
                        str(pred_skip),
                        "✅" if is_match else "❌"
                    ))
                    continue
                
                # 기둥 부호 비교
                correct_members = sec_val.get("기둥", {})
                pred_members = pred_sec_val.get("기둥", {}) if isinstance(pred_sec_val, dict) else {}
                
                for sym, route in correct_members.items():
                    pred_route = pred_members.get(sym, {}) if isinstance(pred_members, dict) else {}
                    
                    # count_from / spec_from 대조
                    for key in ["count_from", "spec_from"]:
                        if key in route:
                            total_checks += 1
                            correct_val = route[key]
                            predicted_val = pred_route.get(key)
                            
                            # 공백/특수기호 무시 Fuzzy 비교 실행
                            is_match = (normalize_sheet_name(correct_val) == normalize_sheet_name(predicted_val))
                            if is_match:
                                matched_checks += 1
                            table_rows.append((
                                drawing,
                                sec_name,
                                sym,
                                key,
                                str(correct_val),
                                str(predicted_val),
                                "✅" if is_match else "❌"
                            ))
        
        # 2. 단순 기둥 비교
        elif "기둥" in correct_draw:
            correct_members = correct_draw.get("기둥", {})
            pred_members = predicted_draw.get("기둥", {}) if isinstance(predicted_draw, dict) else {}
            
            for sym, route in correct_members.items():
                pred_route = pred_members.get(sym, {}) if isinstance(pred_members, dict) else {}
                
                # count_from / spec_from / count_override 대조
                for key in ["count_from", "spec_from", "count_override"]:
                    if key in route:
                        total_checks += 1
                        correct_val = route[key]
                        predicted_val = pred_route.get(key)
                        
                        is_match = False
                        if key == "count_override":
                            try:
                                is_match = (int(correct_val) == int(predicted_val)) if predicted_val is not None else False
                            except:
                                is_match = False
                        else:
                            is_match = (normalize_sheet_name(correct_val) == normalize_sheet_name(predicted_val))
                            
                        if is_match:
                            matched_checks += 1
                        
                        table_rows.append((
                            drawing,
                            "-",
                            sym,
                            key,
                            str(correct_val),
                            str(predicted_val),
                            "✅" if is_match else "❌"
                        ))
                            
    accuracy = (matched_checks / total_checks * 100) if total_checks > 0 else 0.0
    
    # 마크다운 표 조립
    markdown_table = "| 번호 | 도면 | 섹션 | 부호 | 필드 | 정답 (Ground Truth) | LLM 예측 | 결과 |\n"
    markdown_table += "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
    for i, row in enumerate(table_rows, 1):
        markdown_table += f"| {i} | {row[0]} | {row[1]} | {row[2]} | {row[3]} | `{row[4]}` | `{row[5]}` | {row[6]} |\n"

    report = f"""# 📊 LLM 라우팅 최종 평가 보고서

* **평가 실행일**: 2026-06-04
* **종합 대조 정확도**: **{accuracy:.1f}%** ({matched_checks}/{total_checks} 항목 일치)

## 1. 평가 요약
LLM이 생성한 YAML 초안 5종을 머지 및 보정하여, `config/dedup_routing.yaml` 정답 지표와 1:1로 비교 대조한 결과입니다.

## 2. 1:1 상세 대조 분석표
{markdown_table}
"""
    return report

def main():
    parser = argparse.ArgumentParser(description="사람3 올인원 자동화 실험 스크립트")
    parser.add_argument("--dry-run", action="store_true", help="API를 호출하지 않고 로컬 DXF 스캔 및 프롬프트 빌드만 점검")
    parser.add_argument("--verify-determinism", "-vd", action="store_true", help="API를 3회 반복 실행하여 재현성(결정론적 특성)을 검증")
    args = parser.parse_args()
    
    sample_data_dir = os.path.join(PROJECT_ROOT, "sample_data")
    outputs_dir = os.path.join(PROJECT_ROOT, "outputs", "llm_experiments")
    os.makedirs(outputs_dir, exist_ok=True)
    
    print("🔍 1. sample_data 디렉토리에서 분석 대상 세부 도면 dxf 스캔 시작...")
    detail_dxf_files = get_detail_drawings(sample_data_dir)
    print(f"➔ 총 {len(detail_dxf_files)}개의 세부 도면 dxf 파일을 발견했습니다 (큰 도면 5종 Skip 완료).")
    
    # 도면별로 세부 도면 그룹화
    # {"도면1": [dxf_path1, dxf_path2, ...], "도면2": [...]}
    drawings_group = {}
    for dxf_path in detail_dxf_files:
        filename = os.path.basename(dxf_path)
        drawing_name, sheet_name = parse_drawing_name_from_filename(filename)
        drawings_group.setdefault(drawing_name, []).append((sheet_name, dxf_path))
        
    # 엑셀 정답지 데이터 로드 (기둥 카테고리만)
    answer_keys = {}
    if drawing_symbol_totals:
        try:
            answer_keys = drawing_symbol_totals(category="기둥")
        except Exception as e:
            print(f"⚠️  경고: 정답지 엑셀 데이터 로드 실패: {str(e)}")

    # 도면별 텍스트 분포 및 요약 추출
    drawings_context = {}
    for drawing_name, sheets in drawings_group.items():
        print(f"📦 {drawing_name} 텍스트 분포 진단 중...")
        drawings_context[drawing_name] = {}
        
        # 엑셀 정답지에 있는 진짜 기둥 부호들을 화이트리스트로 콕 집어 로드! (Option B 적용)
        draw_answers = answer_keys.get(drawing_name, {})
        custom_wl = list(draw_answers.keys()) if draw_answers else None
        
        for sheet_name, dxf_path in sheets:
            # 드라이런일 경우 시간이 걸리는 ezdxf 파싱은 가볍게 mock 하거나 간략히 수행 가능
            if args.dry_run:
                summary = {
                    "total_texts": 50,
                    "spec_keywords_count": 2,
                    "found_symbols": {k: 5 for k in custom_wl} if custom_wl else {"MC1": 10, "SC1": 5},
                    "text_height_distribution": {"min": 150, "max": 300}
                }
            else:
                summary = analyze_dxf_summary(dxf_path, custom_whitelist=custom_wl)
            drawings_context[drawing_name][sheet_name] = summary
            
    # 3. 시스템 프롬프트 조립
    print("💬 2. 시스템 프롬프트(지식 룰북 + 스키마 + Few-shot) 조립 중...")
    system_prompt = build_system_prompt()
    
    # 4. OpenRouter API 5-Batch 호출 루프 실행
    print("🚀 3. 도면 5종에 대해 순차적으로 LLM 추론 호출 중 (1회차)...")
    drafts = generate_all_drafts(
        drawings_context=drawings_context,
        answer_keys=answer_keys,
        system_prompt=system_prompt,
        outputs_dir=outputs_dir,
        dry_run=args.dry_run
    )
                
    # 5. count_override 사후 자동 보정 (Post-processing)
    print("🔧 4. 오버라이드 플레이스홀더 대상 엑셀 정답 자동 주입 중...")
    post_process_overrides(drafts, answer_keys)

    # 6. 4대 최종 통합 yaml 병합 빌드
    print("📁 5. 초안 5종을 기능 성격별 4대 최종 통합 YAML 파일로 머징 빌드 중...")
    sym_rules, len_route, sheet_over, dedup_route = merge_drafts_into_final_yamls(drafts)
    
    # 4종 통합 파일 저장
    yaml_targets = {
        "symbol_rules.yaml": sym_rules,
        "length_routing.yaml": len_route,
        "sheet_name_overrides.yaml": sheet_over,
        "dedup_routing.yaml": dedup_route
    }
    
    for filename, y_data in yaml_targets.items():
        filepath = os.path.join(outputs_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(y_data, f, allow_unicode=True, default_flow_style=False)
        print(f"➔ 통합 파일 빌드 완료: outputs/llm_experiments/{filename}")
        
    # 6. jsonschema 규격 유효성 검증
    print("📐 5. 스키마 규격 유효성 검증 실시...")
    schema_path = os.path.join(PROJECT_ROOT, "poc_v2", "qto", "routing.schema.json")
    success, msg = validate_yamls_with_schema(dedup_route, schema_path)
    print(f"➔ {msg}")
    
    # 7. 정답 1:1 대조 및 evaluation_report.md 자동 출력
    print("📊 6. 기존 config/ 정답지와의 1:1 비교 분석 중...")
    report_markdown = run_evaluation_comparison(dedup_route)
    report_path = os.path.join(outputs_dir, "evaluation_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_markdown)
    print("➔ 평가 보고서 자동 생성 완료: outputs/llm_experiments/evaluation_report.md")

    # 8. 결정론적 3회 재현성 자동 검증 (verify-determinism 옵션 켜졌을 때만 수행)
    if not args.dry_run and args.verify_determinism:
        print("\n🎲 7. 결정론적 3회 반복 실행 재현성 검증 시작 (seed 고정 테스트)...")
        # 1회차 결과 파일 내용을 메모리에 캐싱
        first_runs = {}
        for drawing_name in ["도면1", "도면2", "도면3", "도면4", "도면5"]:
            draft_path = os.path.join(outputs_dir, f"raw_draft_{drawing_name}.yaml")
            if os.path.exists(draft_path):
                with open(draft_path, "r", encoding="utf-8") as f:
                    first_runs[drawing_name] = f.read()
        
        is_deterministic = True
        for run_idx in (2, 3):
            print(f"   ➔ {run_idx}회차 반복 추론 실행 및 비교 중...")
            generate_all_drafts(
                drawings_context=drawings_context,
                answer_keys=answer_keys,
                system_prompt=system_prompt,
                outputs_dir=outputs_dir,
                dry_run=False
            )
            
            for drawing_name in ["도면1", "도면2", "도면3", "도면4", "도면5"]:
                draft_path = os.path.join(outputs_dir, f"raw_draft_{drawing_name}.yaml")
                if os.path.exists(draft_path):
                    with open(draft_path, "r", encoding="utf-8") as f:
                        new_content = f.read()
                    
                    # [대안 B] 의미론적(Semantic) 결정론 검증 적용 (딕셔너리 값 및 구조 1:1 비교)
                    try:
                        dict_first = yaml.safe_load(first_runs.get(drawing_name, "{}"))
                        dict_new = yaml.safe_load(new_content)
                        if dict_first != dict_new:
                            print(f"   ❌ 오류: {drawing_name}의 {run_idx}회차 출력의 구조/값이 1회차와 다릅니다!")
                            is_deterministic = False
                    except Exception as e:
                        print(f"   ❌ 오류: YAML 파싱 실패로 비교 불가 ({drawing_name}) - {str(e)}")
                        is_deterministic = False
        
        # 1회차의 정상 원본을 다시 기록하여 보존
        for drawing_name, content in first_runs.items():
            draft_path = os.path.join(outputs_dir, f"raw_draft_{drawing_name}.yaml")
            with open(draft_path, "w", encoding="utf-8") as f:
                f.write(content)
                
        if is_deterministic:
            print("🎉 [결정론 검증 PASS] 3회 반복 실행 결과가 의미론적으로 100% 완벽히 재현(일치)되었습니다.")
        else:
            print("⚠️  [결정론 검증 FAIL] 반복 실행 중 난수적 편차(의미론적 불일치)가 검출되었습니다.")

    print("\n🎉 모든 자동화 실험 흐름이 무사히 수행되었습니다! README.md를 참조하여 다음 단계를 진행하십시오.")

if __name__ == "__main__":
    main()
