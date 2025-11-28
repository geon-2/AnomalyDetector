"""
ECS (Elastic Common Schema) 9.2.0 기반 로그 정규화 모듈

이 모듈은 LogHub 데이터셋의 다양한 로그 형식을 ECS 9.2.0 스키마에 맞게 정규화합니다.

ECS 9.2.0 참조:
- Base fields: @timestamp, message, labels, tags
- Log fields: log.level, log.logger, log.file.path, log.syslog.*
- Event fields: event.id, event.category, event.type, event.kind, event.outcome
- Process fields: process.name, process.pid, process.command_line
- 기타: host.*, network.*, http.*, user.* 등

참고: ECS 9.2.0 스키마 정의는 ecs-9.2.0/schemas/ 디렉토리를 참조하세요.
"""

import yaml
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import hashlib
import os

# ECS 버전 정보
ECS_VERSION = "9.2.0"


class ECSNormalizer:
    """
    ECS (Elastic Common Schema) 9.2.0 기반 로그 정규화 클래스
    
    LogHub 데이터셋의 구조화된 로그를 ECS 9.2.0 형식으로 변환합니다.
    
    주요 기능:
    - @timestamp: ISO8601 형식의 타임스탬프 정규화
    - log.level: 로그 레벨 정규화 (info, warn, error, debug, fatal)
    - event.id: 이벤트 고유 ID 생성
    - process.name: 프로세스명 추출
    - pattern_extraction: 정규식 기반 필드 추출
    - conditional: 조건부 필드 설정
    
    ECS 9.2.0 필드 매핑:
    - @timestamp (base): 이벤트 발생 시간 (ISO8601)
    - message (base): 로그 메시지
    - log.level (log): 로그 레벨
    - log.source (custom): 로그 소스 (LogHub 데이터셋명)
    - event.id (event): 이벤트 고유 식별자
    - process.name (process): 프로세스명
    - host.name (host): 호스트명 (해당 시)
    
    참고: 일부 필드(log.source, log.category 등)는 ECS 표준에 없는 
    커스텀 필드이지만, LogHub 데이터셋 분류를 위해 사용됩니다.
    """
    
    def __init__(self, schemas_dir: str, mappings_dir: str):
        """
        Args:
            schemas_dir: ECS 스키마 정의 파일 디렉토리
            mappings_dir: 소스별 필드 매핑 정의 파일 디렉토리
        """
        self.schemas_dir = schemas_dir
        self.mappings_dir = mappings_dir
        self.ecs_version = ECS_VERSION

        # 스키마 로딩 (필요시 사용, 지금은 구조만 유지)
        self.schemas = self._load_schemas()
        # 매핑 로딩
        self.mappings = self._load_mappings()

    # ---------- public API ----------

    def normalize(self, raw_log: Dict[str, Any], source: str) -> Dict[str, Any]:
        """
        LogHub 구조화 로그를 ECS 9.2.0 형식으로 정규화합니다.
        
        Args:
            raw_log: LogHub structured CSV에서 파싱된 필드 dict
                   (예: {"Date": "081109", "Time": "203518", "Level": "INFO", ...})
            source: 로그 소스 타입 ("hdfs", "hadoop", "openstack", "android", ...)
        
        Returns:
            ECS 9.2.0 형식의 정규화된 로그 dict:
            {
                "@timestamp": "2008-11-09T20:35:18+00:00",  # ECS base
                "message": "Receiving block blk_...",         # ECS base
                "log": {
                    "level": "info",                         # ECS log.level
                    "source": "hdfs"                         # custom (LogHub dataset)
                },
                "event": {
                    "id": "a1b2c3d4..."                       # ECS event.id
                },
                "process": {
                    "name": "dfs.DataNode$DataXceiver"       # ECS process.name
                },
                ...
            }
        
        Raises:
            ValueError: 알 수 없는 source 타입인 경우
        """
        if source not in self.mappings:
            raise ValueError(f"Unknown source: {source}")

        mapping = self.mappings[source]
        normalized: Dict[str, Any] = {}

        # 1. defaults 적용
        for k, v in mapping.get("defaults", {}).items():
            self._set_nested(normalized, k, v)

        # 2. field_mapping 적용
        for src_field, dst_field in mapping.get("field_mapping", {}).items():
            if src_field not in raw_log:
                continue
            value = raw_log[src_field]
            # 특별 처리: @timestamp, log.level, event.is_anomaly 등
            if dst_field == "@timestamp":
                # 타임스탬프는 전체적으로 한 번에 파싱하므로 여기서는 skip
                # (아래 _apply_timestamp 에서 처리)
                continue
            if dst_field == "event.is_anomaly":
                value = self._to_bool_label(value)
            if dst_field == "log.level":
                value = self._normalize_level(value)

            self._set_nested(normalized, dst_field, value)

        # 3. timestamp 파싱
        self._apply_timestamp(normalized, raw_log, mapping)

        # 4. pattern_extraction 적용
        self._apply_patterns(normalized, raw_log, mapping)

        # 5. conditional 규칙 적용
        self._apply_conditionals(normalized, raw_log, mapping)

        # 6. message 기본값 보장 (없으면 Content, raw_log 전체 등에서 보완)
        if "message" not in normalized:
            if "Content" in raw_log:
                normalized["message"] = raw_log["Content"]
            else:
                normalized["message"] = str(raw_log)

        # 7. event.id 생성
        if "event" not in normalized:
            normalized["event"] = {}
        if "id" not in normalized["event"]:
            normalized["event"]["id"] = self._generate_event_id(normalized)

        return normalized

    # ---------- internal: loading ----------

    def _load_schemas(self) -> Dict[str, Dict[str, Any]]:
        schemas = {}
        for filename in os.listdir(self.schemas_dir):
            if not filename.endswith(".yaml"):
                continue
            path = os.path.join(self.schemas_dir, filename)
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            schemas[filename] = data
        return schemas

    def _load_mappings(self) -> Dict[str, Dict[str, Any]]:
        mappings = {}
        for filename in os.listdir(self.mappings_dir):
            if not filename.endswith(".yaml"):
                continue
            path = os.path.join(self.mappings_dir, filename)
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            src = data.get("_meta", {}).get("source")
            if src:
                mappings[src] = data
        return mappings

    # ---------- internal: helpers ----------

    def _set_nested(self, obj: Dict[str, Any], path: str, value: Any):
        if value is None:
            return
        keys = path.split(".")
        cur = obj
        for key in keys[:-1]:
            if key not in cur or not isinstance(cur[key], dict):
                cur[key] = {}
            cur = cur[key]
        cur[keys[-1]] = value

    def _get_nested(self, obj: Dict[str, Any], path: str) -> Optional[Any]:
        keys = path.split(".")
        cur: Any = obj
        for key in keys:
            if not isinstance(cur, dict) or key not in cur:
                return None
            cur = cur[key]
        return cur

    def _to_bool_label(self, v: Any) -> Optional[bool]:
        # LogHub 라벨 형식에 맞게 조정
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        s = str(v).strip()
        if s in ("1", "true", "True", "anomaly"):
            return True
        if s in ("0", "false", "False", "-", "normal"):
            return False
        return None

    def _normalize_level(self, level: Any) -> str:
        if level is None:
            return "unknown"
        s = str(level).upper()
        mapping = {
            "I": "info",
            "INFO": "info",
            "INFORMATION": "info",
            "W": "warn",
            "WARN": "warn",
            "WARNING": "warn",
            "E": "error",
            "ERR": "error",
            "ERROR": "error",
            "D": "debug",
            "DEBUG": "debug",
            "F": "fatal",
            "FATAL": "fatal",
            "CRITICAL": "fatal",
            "FAILURE": "fatal",
            "V": "debug",  # android verbose
        }
        return mapping.get(s, "unknown")

    def _apply_timestamp(self, normalized: Dict[str, Any],
                         raw_log: Dict[str, Any],
                         mapping: Dict[str, Any]):
        # 이미 @timestamp 있으면 그대로 두고, 없을 때만 계산
        if "@timestamp" in normalized:
            return

        ts_cfg = mapping.get("timestamp")
        if not ts_cfg:
            # fallback: 없으면 현재 시간
            normalized["@timestamp"] = datetime.now(timezone.utc).isoformat()
            return

        fields: List[str] = ts_cfg.get("fields", [])
        fmt: str = ts_cfg.get("format", "")
        tz = ts_cfg.get("timezone", "UTC")

        # epoch 지원
        if fmt == "epoch":
            for f in fields:
                if f in raw_log and raw_log[f] not in (None, ""):
                    try:
                        ts_int = int(str(raw_log[f]))
                        dt = datetime.fromtimestamp(ts_int, tz=timezone.utc)
                        normalized["@timestamp"] = dt.isoformat()
                        return
                    except Exception:
                        continue
            normalized["@timestamp"] = datetime.now(timezone.utc).isoformat()
            return

        # 문자열 조합
        parts = []
        for f in fields:
            if f in raw_log and raw_log[f] not in (None, ""):
                parts.append(str(raw_log[f]).strip())
        if not parts:
            normalized["@timestamp"] = datetime.now(timezone.utc).isoformat()
            return

        ts_str = " ".join(parts)
        try:
            # 쉼표로 구분된 밀리초를 점으로 변환 (Python strptime은 %f가 점을 기대함)
            if "," in ts_str and "%f" in fmt:
                ts_str = ts_str.replace(",", ".")
                fmt = fmt.replace(",%f", ".%f")  # 포맷 문자열도 함께 수정
            # timezone은 여기서는 단순히 UTC로만 맞춘다
            dt_naive = datetime.strptime(ts_str, fmt)
            dt = dt_naive.replace(tzinfo=timezone.utc)
            normalized["@timestamp"] = dt.isoformat()
        except Exception:
            normalized["@timestamp"] = datetime.now(timezone.utc).isoformat()

    def _apply_patterns(self, normalized: Dict[str, Any],
                        raw_log: Dict[str, Any],
                        mapping: Dict[str, Any]):
        pat_cfg = mapping.get("pattern_extraction", [])
        if not pat_cfg:
            return

        # message / Content 를 기본 검색 대상
        content = None
        if "Content" in raw_log:
            content = str(raw_log["Content"])
        elif "message" in raw_log:
            content = str(raw_log["message"])
        else:
            content = " ".join(str(v) for v in raw_log.values())

        for rule in pat_cfg:
            field = rule.get("field")
            if not field:
                continue

            # 두 가지 모드:
            # 1) pattern: 단일 정규식
            # 2) patterns: [{pattern, value}, ...]
            if "pattern" in rule:
                pattern = rule["pattern"]
                m = re.search(pattern, content)
                if m:
                    val = m.group(1) if m.groups() else m.group(0)
                    self._set_nested(normalized, field, val)

            if "patterns" in rule:
                for p in rule["patterns"]:
                    patt = p.get("pattern")
                    val = p.get("value")
                    if not patt or val is None:
                        continue
                    if re.search(patt, content):
                        self._set_nested(normalized, field, val)
                        break

    def _apply_conditionals(self, normalized: Dict[str, Any],
                            raw_log: Dict[str, Any],
                            mapping: Dict[str, Any]):
        conds = mapping.get("conditional", [])
        for rule in conds:
            cond = rule.get("condition", {})
            set_fields = rule.get("set", {})
            if not cond or not set_fields:
                continue

            field = cond.get("field")
            contains = cond.get("contains")
            equals = cond.get("equals")

            src_val = raw_log.get(field)
            if src_val is None:
                continue
            s = str(src_val)

            ok = True
            if contains is not None and contains not in s:
                ok = False
            if equals is not None and s != equals:
                ok = False

            if ok:
                for k, v in set_fields.items():
                    self._set_nested(normalized, k, v)

    def _generate_event_id(self, normalized: Dict[str, Any]) -> str:
        base = f"{normalized.get('@timestamp', '')}|{normalized.get('message', '')}"
        h = hashlib.md5(base.encode("utf-8")).hexdigest()
        return h[:16]

