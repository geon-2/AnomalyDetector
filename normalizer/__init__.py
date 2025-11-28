"""
ECS Normalizer 패키지
"""

# 순환 import 방지: normalizer.py에서 직접 import
from .normalizer import ECSNormalizer, ECS_VERSION

__all__ = ['ECSNormalizer', 'ECS_VERSION']
__version__ = '1.0.0'

