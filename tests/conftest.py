"""共通フィクスチャ。

データ生成を小さな n で共通化し、後続テスト(IC-2/IC-4)でも再利用できるよう汎用化する。
ファイル I/O(build) は避け、`generate_data._generate` を直接呼ぶ。
"""

from __future__ import annotations

import pytest

from generator import generate_data
from generator.generate_data import Profile

# テスト全体で使う小さな患者数。再現性・スキーマ確認には十分。
SMALL_N = 30


@pytest.fixture
def small_profile() -> Profile:
    """小さな n の汎用 Profile(raw 相当: shift=0.0)。"""
    return Profile(name="test", seed=1234, n_patients=SMALL_N, shift=0.0)


@pytest.fixture
def dataset(small_profile: Profile) -> dict:
    """`_generate(small_profile)` の結果。後続 IC でも再利用する汎用フィクスチャ。"""
    return generate_data._generate(small_profile)


@pytest.fixture
def raw_dataset() -> dict:
    """raw 相当の小 n データ(shift=0.0)。syn_dataset と同 n。"""
    profile = Profile(name="raw", seed=20210101, n_patients=SMALL_N, shift=0.0)
    return generate_data._generate(profile)


@pytest.fixture
def syn_dataset() -> dict:
    """synthetic 相当の小 n データ(shift=1.0)。raw_dataset と同 n。"""
    profile = Profile(name="synthetic", seed=99999, n_patients=SMALL_N, shift=1.0)
    return generate_data._generate(profile)
