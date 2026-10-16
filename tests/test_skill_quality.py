"""Skill 契约检查：fixture 是记录式样例，不是模型执行证据。"""
from pathlib import Path
import ast
import json
import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/'skills/mijia-ac-control'


def frontmatter():
    text = (SKILL/'SKILL.md').read_text(encoding='utf-8')
    raw = text.split('---', 2)[1]
    # 本目标只采用单行顶层标量/列表；缩进字段不能冒充顶层。
    return {line.split(':',1)[0]: line.split(':',1)[1].strip()
            for line in raw.splitlines() if ':' in line and not line[0].isspace()}


def test_frontmatter_types_and_platforms():
    meta = frontmatter()
    assert set(('name','description','version','author','license','platforms')) <= meta.keys()
    assert ast.literal_eval(meta['platforms']) == ['windows','macos','linux']
    assert ast.literal_eval(meta['version']) == '0.1.0'
    assert ast.literal_eval(meta['author']) == 'yyyzl'
    assert 'metadata' not in meta
    assert len(meta['description']) <= 60


def test_ci_required_platforms_and_entry():
    text = (ROOT/'.github/workflows/ci.yml').read_text()
    assert 'os: [ubuntu-latest, windows-latest, macos-latest]' in text
    assert "python: ['3.11', '3.12']" in text
    for command in ['uv sync --locked', 'mijia-ac --help', 'timeout=60', 'tools/check_public_tree.py']:
        assert command in text


def valid_output(output):
    required = {'target/config', 'requested action', 'preview/executed', 'before', 'after',
                'independent readback', 'match/failure', 'side effects', 'physical evidence/unknown'}
    if not required <= output.keys():
        return False
    if output['physical evidence/unknown'] != 'unknown':
        return False
    if output['preview/executed'] == 'preview' and (output['after'] != 'unknown' or output['independent readback'] != 'none'):
        return False
    return True


def test_output_fixtures_and_negative_mutations():
    cases = [json.loads(line) for line in (SKILL/'evals/output/cases.jsonl').read_text(encoding='utf-8').splitlines()]
    assert {c['id'] for c in cases} == {'relative','preview','off-denied','failure','mode-side-effect','room-temperature'}
    for case in cases:
        assert case['metadata']['evidence_type'] == 'fixture'
        output = json.loads(case['with_skill_output'])
        assert valid_output(output)
        for key, value in case['metadata']['expected'].items():
            assert output[key] == value
        broken = dict(output)
        del broken['side effects']
        assert not valid_output(broken)
        broken = dict(output, **{'physical evidence/unknown':'confirmed cooling'})
        assert not valid_output(broken)


def test_trigger_cases_coverage():
    data = json.loads((SKILL/'evals/trigger_cases.json').read_text(encoding='utf-8'))
    for bucket in ('should_trigger','should_not_trigger','near_neighbor'):
        assert {c['language'] for c in data[bucket]} == {'zh','en'}
    description = frontmatter()['description']
    for branch in ('状态','设定温度','开关','模式'):
        assert branch in description
