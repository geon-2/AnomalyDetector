#!/usr/bin/env python3
"""
ECS 9.2.0 Normalizer 테스트 스크립트

loghub-master의 structured CSV 파일을 읽어서 ECS 9.2.0 형식으로 정규화하는지 테스트합니다.
"""

import csv
import json
import os
import sys
from pathlib import Path
from normalizer import ECSNormalizer

# 경로 설정
LOGHUB_DIR = Path("/Users/gunlee/Downloads/loghub-master")
NORMALIZER_DIR = Path(__file__).parent

# 테스트할 로그 소스와 매핑
TEST_CASES = [
    {
        "source": "hdfs",
        "csv_file": LOGHUB_DIR / "HDFS" / "HDFS_2k.log_structured.csv",
        "sample_count": 5
    },
    {
        "source": "openstack",
        "csv_file": LOGHUB_DIR / "OpenStack" / "OpenStack_2k.log_structured.csv",
        "sample_count": 5
    },
    {
        "source": "hadoop",
        "csv_file": LOGHUB_DIR / "Hadoop" / "Hadoop_2k.log_structured.csv",
        "sample_count": 5
    },
    {
        "source": "android",
        "csv_file": LOGHUB_DIR / "Android" / "Android_2k.log_structured.csv",
        "sample_count": 5
    },
]


def csv_to_dict_list(csv_path: Path, max_rows: int = None) -> list:
    """CSV 파일을 읽어서 dict 리스트로 변환"""
    if not csv_path.exists():
        print(f"❌ 파일 없음: {csv_path}")
        return []
    
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if max_rows and i >= max_rows:
                break
            # 빈 값 제거 및 정리
            cleaned = {k: v.strip() if v else None for k, v in row.items()}
            rows.append(cleaned)
    return rows


def test_normalizer():
    """Normalizer 테스트 실행"""
    print("=" * 80)
    print("ECS 9.2.0 Normalizer 테스트 시작")
    print("=" * 80)
    
    # Normalizer 초기화
    schemas_dir = NORMALIZER_DIR / "schemas"
    mappings_dir = NORMALIZER_DIR / "mappings"
    
    try:
        normalizer = ECSNormalizer(
            schemas_dir=str(schemas_dir),
            mappings_dir=str(mappings_dir)
        )
        print(f"✅ Normalizer 초기화 완료")
        print(f"   - ECS 버전: {normalizer.ecs_version}")
        print(f"   - Schemas: {schemas_dir}")
        print(f"   - Mappings: {mappings_dir}")
        print(f"   - 로드된 소스: {list(normalizer.mappings.keys())}")
        print()
    except Exception as e:
        print(f"❌ Normalizer 초기화 실패: {e}")
        return False
    
    # 각 테스트 케이스 실행
    all_passed = True
    for test_case in TEST_CASES:
        source = test_case["source"]
        csv_file = test_case["csv_file"]
        sample_count = test_case["sample_count"]
        
        print("-" * 80)
        print(f"📋 테스트: {source.upper()}")
        print(f"   파일: {csv_file.name}")
        print("-" * 80)
        
        # CSV 읽기
        raw_logs = csv_to_dict_list(csv_file, max_rows=sample_count)
        if not raw_logs:
            print(f"   ⚠️  로그 데이터 없음")
            all_passed = False
            continue
        
        print(f"   📊 샘플 {len(raw_logs)}개 로드")
        print()
        
        # 각 로그 정규화 테스트
        success_count = 0
        for idx, raw_log in enumerate(raw_logs, 1):
            try:
                normalized = normalizer.normalize(raw_log, source=source)
                
                # 필수 필드 검증
                required_fields = ["@timestamp", "message", "event.id"]
                missing = [f for f in required_fields if not _has_field(normalized, f)]
                
                if missing:
                    print(f"   ⚠️  샘플 #{idx}: 필수 필드 누락 - {missing}")
                    print(f"      원본: {raw_log.get('Content', raw_log.get('Content', 'N/A'))[:80]}")
                else:
                    success_count += 1
                    if idx <= 2:  # 처음 2개만 상세 출력
                        print(f"   ✅ 샘플 #{idx}: 정규화 성공")
                        print(f"      원본: {raw_log.get('Content', raw_log.get('Content', 'N/A'))[:60]}...")
                        print(f"      → @timestamp: {normalized.get('@timestamp', 'N/A')}")
                        print(f"      → log.level: {_get_nested(normalized, 'log.level', 'N/A')}")
                        print(f"      → message: {normalized.get('message', 'N/A')[:60]}...")
                        if 'process' in normalized:
                            print(f"      → process.name: {normalized.get('process', {}).get('name', 'N/A')}")
                        if 'distributed' in normalized:
                            dist = normalized.get('distributed', {})
                            if dist:
                                print(f"      → distributed: {dist}")
                        print()
                
            except Exception as e:
                print(f"   ❌ 샘플 #{idx}: 정규화 실패 - {e}")
                print(f"      원본: {raw_log.get('Content', str(raw_log)[:80])}")
                all_passed = False
        
        print(f"   📈 결과: {success_count}/{len(raw_logs)} 성공")
        print()
    
    # 최종 결과
    print("=" * 80)
    if all_passed:
        print("✅ 모든 테스트 통과!")
    else:
        print("⚠️  일부 테스트 실패 (위 로그 확인)")
    print("=" * 80)
    
    return all_passed


def _has_field(obj: dict, path: str) -> bool:
    """중첩된 필드 존재 여부 확인"""
    keys = path.split(".")
    cur = obj
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return False
        cur = cur[key]
    return True


def _get_nested(obj: dict, path: str, default=None):
    """중첩된 필드 값 가져오기"""
    keys = path.split(".")
    cur = obj
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


if __name__ == "__main__":
    success = test_normalizer()
    sys.exit(0 if success else 1)

