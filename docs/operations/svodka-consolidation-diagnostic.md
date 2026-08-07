# Svodka consolidation diagnostic

Workflow run: 31228035293 attempt 1

| Gate | Outcome |
|---|---|
| install | success |
| edit | failure |
| read-only Telegram discovery | success |
| format | failure |
| ruff | failure |
| mypy | failure |
| pytest | failure |
| candidate | success |

## install
```text
Obtaining file:///home/runner/work/video-channel-manager/video-channel-manager
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Checking if build backend supports build_editable: started
  Checking if build backend supports build_editable: finished with status 'done'
  Getting requirements to build editable: started
  Getting requirements to build editable: finished with status 'done'
  Preparing editable metadata (pyproject.toml): started
  Preparing editable metadata (pyproject.toml): finished with status 'done'
Collecting alembic<2,>=1.14 (from video-channel-manager==0.1.0)
  Downloading alembic-1.19.0-py3-none-any.whl.metadata (7.3 kB)
Collecting httpx<1,>=0.28 (from video-channel-manager==0.1.0)
  Downloading httpx-0.28.1-py3-none-any.whl.metadata (7.1 kB)
Collecting platformdirs<5,>=4.3 (from video-channel-manager==0.1.0)
  Downloading platformdirs-4.11.1-py3-none-any.whl.metadata (5.5 kB)
Collecting pydantic<3,>=2.10 (from video-channel-manager==0.1.0)
  Downloading pydantic-2.13.4-py3-none-any.whl.metadata (109 kB)
Collecting pydantic-settings<3,>=2.7 (from video-channel-manager==0.1.0)
  Downloading pydantic_settings-2.15.0-py3-none-any.whl.metadata (3.9 kB)
Collecting python-dotenv<2,>=1.0 (from video-channel-manager==0.1.0)
  Downloading python_dotenv-1.2.2-py3-none-any.whl.metadata (27 kB)
Collecting rich<15,>=13.9 (from video-channel-manager==0.1.0)
  Downloading rich-14.3.4-py3-none-any.whl.metadata (18 kB)
Collecting sqlalchemy<3,>=2.0.36 (from video-channel-manager==0.1.0)
  Downloading sqlalchemy-2.0.51-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (9.5 kB)
Collecting tenacity<10,>=9 (from video-channel-manager==0.1.0)
  Downloading tenacity-9.1.4-py3-none-any.whl.metadata (1.2 kB)
Collecting typer<1,>=0.15 (from video-channel-manager==0.1.0)
  Downloading typer-0.27.1-py3-none-any.whl.metadata (16 kB)
Collecting mypy<2,>=1.14 (from video-channel-manager==0.1.0)
  Downloading mypy-1.20.2-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.4 kB)
Collecting pip-audit<3,>=2.9 (from video-channel-manager==0.1.0)
  Downloading pip_audit-2.10.1-py3-none-any.whl.metadata (28 kB)
Collecting pytest<10,>=8.3 (from video-channel-manager==0.1.0)
  Downloading pytest-9.1.1-py3-none-any.whl.metadata (7.6 kB)
Collecting pytest-cov<8,>=6 (from video-channel-manager==0.1.0)
  Downloading pytest_cov-7.1.0-py3-none-any.whl.metadata (32 kB)
Collecting ruff<1,>=0.9 (from video-channel-manager==0.1.0)
  Downloading ruff-0.16.2-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (26 kB)
Collecting Mako (from alembic<2,>=1.14->video-channel-manager==0.1.0)
  Downloading mako-1.4.1-py3-none-any.whl.metadata (2.9 kB)
Collecting typing-extensions>=4.12 (from alembic<2,>=1.14->video-channel-manager==0.1.0)
  Downloading typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
Collecting anyio (from httpx<1,>=0.28->video-channel-manager==0.1.0)
  Downloading anyio-4.14.2-py3-none-any.whl.metadata (4.6 kB)
Collecting certifi (from httpx<1,>=0.28->video-channel-manager==0.1.0)
  Downloading certifi-2026.7.22-py3-none-any.whl.metadata (2.5 kB)
Collecting httpcore==1.* (from httpx<1,>=0.28->video-channel-manager==0.1.0)
  Downloading httpcore-1.0.9-py3-none-any.whl.metadata (21 kB)
Collecting idna (from httpx<1,>=0.28->video-channel-manager==0.1.0)
  Downloading idna-3.18-py3-none-any.whl.metadata (6.1 kB)
Collecting h11>=0.16 (from httpcore==1.*->httpx<1,>=0.28->video-channel-manager==0.1.0)
  Downloading h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
Collecting mypy_extensions>=1.0.0 (from mypy<2,>=1.14->video-channel-manager==0.1.0)
  Downloading mypy_extensions-1.1.0-py3-none-any.whl.metadata (1.1 kB)
Collecting pathspec>=1.0.0 (from mypy<2,>=1.14->video-channel-manager==0.1.0)
  Downloading pathspec-1.1.1-py3-none-any.whl.metadata (14 kB)
Collecting librt>=0.8.0 (from mypy<2,>=1.14->video-channel-manager==0.1.0)
  Downloading librt-0.15.0-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (1.3 kB)
Collecting CacheControl>=0.13.0 (from CacheControl[filecache]>=0.13.0->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading cachecontrol-0.14.4-py3-none-any.whl.metadata (3.1 kB)
Collecting cyclonedx-python-lib<12,>=5 (from pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading cyclonedx_python_lib-11.11.0-py3-none-any.whl.metadata (6.9 kB)
Collecting packaging>=23.0.0 (from pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Using cached packaging-26.3-py3-none-any.whl.metadata (3.5 kB)
Collecting pip-api>=0.0.28 (from pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading pip_api-0.0.34-py3-none-any.whl.metadata (6.6 kB)
Collecting pip-requirements-parser>=32.0.0 (from pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading pip_requirements_parser-32.0.1-py3-none-any.whl.metadata (9.3 kB)
Collecting requests>=2.31.0 (from pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading requests-2.34.2-py3-none-any.whl.metadata (4.8 kB)
Collecting tomli>=2.2.1 (from pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading tomli-2.4.1-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (10 kB)
Collecting tomli-w>=1.2.0 (from pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading tomli_w-1.2.0-py3-none-any.whl.metadata (5.7 kB)
Collecting license-expression<31,>=30 (from cyclonedx-python-lib<12,>=5->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading license_expression-30.4.4-py3-none-any.whl.metadata (11 kB)
Collecting packageurl-python<2,>=0.11 (from cyclonedx-python-lib<12,>=5->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading packageurl_python-0.17.6-py3-none-any.whl.metadata (5.1 kB)
Collecting py-serializable<3.0.0,>=2.1.0 (from cyclonedx-python-lib<12,>=5->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading py_serializable-2.1.0-py3-none-any.whl.metadata (4.3 kB)
Collecting sortedcontainers<3.0.0,>=2.4.0 (from cyclonedx-python-lib<12,>=5->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading sortedcontainers-2.4.0-py2.py3-none-any.whl.metadata (10 kB)
Collecting boolean.py>=4.0 (from license-expression<31,>=30->cyclonedx-python-lib<12,>=5->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading boolean_py-5.0-py3-none-any.whl.metadata (2.3 kB)
Collecting defusedxml<0.8.0,>=0.7.1 (from py-serializable<3.0.0,>=2.1.0->cyclonedx-python-lib<12,>=5->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading defusedxml-0.7.1-py2.py3-none-any.whl.metadata (32 kB)
Collecting annotated-types>=0.6.0 (from pydantic<3,>=2.10->video-channel-manager==0.1.0)
  Downloading annotated_types-0.8.0-py3-none-any.whl.metadata (15 kB)
Collecting pydantic-core==2.46.4 (from pydantic<3,>=2.10->video-channel-manager==0.1.0)
  Downloading pydantic_core-2.46.4-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.6 kB)
Collecting typing-inspection>=0.4.2 (from pydantic<3,>=2.10->video-channel-manager==0.1.0)
  Downloading typing_inspection-0.4.2-py3-none-any.whl.metadata (2.6 kB)
Collecting iniconfig>=1.0.1 (from pytest<10,>=8.3->video-channel-manager==0.1.0)
  Downloading iniconfig-2.3.0-py3-none-any.whl.metadata (2.5 kB)
Collecting pluggy<2,>=1.5 (from pytest<10,>=8.3->video-channel-manager==0.1.0)
  Downloading pluggy-1.6.0-py3-none-any.whl.metadata (4.8 kB)
Collecting pygments>=2.7.2 (from pytest<10,>=8.3->video-channel-manager==0.1.0)
  Downloading pygments-2.20.0-py3-none-any.whl.metadata (2.5 kB)
Collecting coverage>=7.10.6 (from coverage[toml]>=7.10.6->pytest-cov<8,>=6->video-channel-manager==0.1.0)
  Downloading coverage-7.15.4-cp311-cp311-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl.metadata (8.6 kB)
Collecting markdown-it-py>=2.2.0 (from rich<15,>=13.9->video-channel-manager==0.1.0)
  Downloading markdown_it_py-4.2.0-py3-none-any.whl.metadata (7.4 kB)
Collecting greenlet>=1 (from sqlalchemy<3,>=2.0.36->video-channel-manager==0.1.0)
  Downloading greenlet-3.5.4-cp311-cp311-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl.metadata (3.8 kB)
Collecting shellingham>=1.3.0 (from typer<1,>=0.15->video-channel-manager==0.1.0)
  Downloading shellingham-1.5.4-py2.py3-none-any.whl.metadata (3.5 kB)
Collecting annotated-doc>=0.0.2 (from typer<1,>=0.15->video-channel-manager==0.1.0)
  Downloading annotated_doc-0.0.5-py3-none-any.whl.metadata (6.5 kB)
Collecting msgpack<2.0.0,>=0.5.2 (from CacheControl>=0.13.0->CacheControl[filecache]>=0.13.0->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading msgpack-1.2.1-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (8.3 kB)
Collecting filelock>=3.8.0 (from CacheControl[filecache]>=0.13.0->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading filelock-3.32.2-py3-none-any.whl.metadata (2.0 kB)
Collecting mdurl~=0.1 (from markdown-it-py>=2.2.0->rich<15,>=13.9->video-channel-manager==0.1.0)
  Downloading mdurl-0.1.2-py3-none-any.whl.metadata (1.6 kB)
Requirement already satisfied: pip in /opt/hostedtoolcache/Python/3.11.15/x64/lib/python3.11/site-packages (from pip-api>=0.0.28->pip-audit<3,>=2.9->video-channel-manager==0.1.0) (26.1.2)
Collecting pyparsing (from pip-requirements-parser>=32.0.0->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading pyparsing-3.3.2-py3-none-any.whl.metadata (5.8 kB)
Collecting charset_normalizer<4,>=2 (from requests>=2.31.0->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading charset_normalizer-3.4.9-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (41 kB)
Collecting urllib3<3,>=1.26 (from requests>=2.31.0->pip-audit<3,>=2.9->video-channel-manager==0.1.0)
  Downloading urllib3-2.7.0-py3-none-any.whl.metadata (6.9 kB)
Collecting MarkupSafe>=2.0 (from Mako->alembic<2,>=1.14->video-channel-manager==0.1.0)
  Downloading markupsafe-3.0.3-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.7 kB)
Downloading alembic-1.19.0-py3-none-any.whl (265 kB)
Downloading httpx-0.28.1-py3-none-any.whl (73 kB)
Downloading httpcore-1.0.9-py3-none-any.whl (78 kB)
Downloading mypy-1.20.2-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (14.6 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 14.6/14.6 MB 124.4 MB/s  0:00:00
Downloading pip_audit-2.10.1-py3-none-any.whl (62 kB)
Downloading cyclonedx_python_lib-11.11.0-py3-none-any.whl (528 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 528.7/528.7 kB 74.2 MB/s  0:00:00
Downloading license_expression-30.4.4-py3-none-any.whl (120 kB)
Downloading packageurl_python-0.17.6-py3-none-any.whl (36 kB)
Downloading platformdirs-4.11.1-py3-none-any.whl (23 kB)
Downloading py_serializable-2.1.0-py3-none-any.whl (23 kB)
Downloading defusedxml-0.7.1-py2.py3-none-any.whl (25 kB)
Downloading pydantic-2.13.4-py3-none-any.whl (472 kB)
Downloading pydantic_core-2.46.4-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (2.1 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.1/2.1 MB 222.4 MB/s  0:00:00
Downloading pydantic_settings-2.15.0-py3-none-any.whl (69 kB)
Downloading pytest-9.1.1-py3-none-any.whl (386 kB)
Downloading pluggy-1.6.0-py3-none-any.whl (20 kB)
Downloading pytest_cov-7.1.0-py3-none-any.whl (22 kB)
Downloading python_dotenv-1.2.2-py3-none-any.whl (22 kB)
Downloading rich-14.3.4-py3-none-any.whl (310 kB)
Downloading pygments-2.20.0-py3-none-any.whl (1.2 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.2/1.2 MB 112.7 MB/s  0:00:00
Downloading ruff-0.16.2-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (11.5 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 11.5/11.5 MB 284.8 MB/s  0:00:00
Downloading sortedcontainers-2.4.0-py2.py3-none-any.whl (29 kB)
Downloading sqlalchemy-2.0.51-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (3.3 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3.3/3.3 MB 195.2 MB/s  0:00:00
Downloading tenacity-9.1.4-py3-none-any.whl (28 kB)
Downloading typer-0.27.1-py3-none-any.whl (122 kB)
Downloading typing_extensions-4.16.0-py3-none-any.whl (45 kB)
Downloading annotated_doc-0.0.5-py3-none-any.whl (5.3 kB)
Downloading annotated_types-0.8.0-py3-none-any.whl (13 kB)
Downloading boolean_py-5.0-py3-none-any.whl (26 kB)
Downloading cachecontrol-0.14.4-py3-none-any.whl (22 kB)
Downloading msgpack-1.2.1-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (423 kB)
Downloading coverage-7.15.4-cp311-cp311-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl (255 kB)
Downloading filelock-3.32.2-py3-none-any.whl (98 kB)
Downloading greenlet-3.5.4-cp311-cp311-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl (624 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 624.7/624.7 kB 93.1 MB/s  0:00:00
Downloading h11-0.16.0-py3-none-any.whl (37 kB)
Downloading iniconfig-2.3.0-py3-none-any.whl (7.5 kB)
Downloading librt-0.15.0-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (516 kB)
Downloading markdown_it_py-4.2.0-py3-none-any.whl (91 kB)
Downloading mdurl-0.1.2-py3-none-any.whl (10.0 kB)
Downloading mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
Using cached packaging-26.3-py3-none-any.whl (129 kB)
Downloading pathspec-1.1.1-py3-none-any.whl (57 kB)
Downloading pip_api-0.0.34-py3-none-any.whl (120 kB)
Downloading pip_requirements_parser-32.0.1-py3-none-any.whl (35 kB)
Downloading requests-2.34.2-py3-none-any.whl (73 kB)
Downloading charset_normalizer-3.4.9-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (221 kB)
Downloading idna-3.18-py3-none-any.whl (65 kB)
Downloading urllib3-2.7.0-py3-none-any.whl (131 kB)
Downloading certifi-2026.7.22-py3-none-any.whl (136 kB)
Downloading shellingham-1.5.4-py2.py3-none-any.whl (9.8 kB)
Downloading tomli-2.4.1-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (243 kB)
Downloading tomli_w-1.2.0-py3-none-any.whl (6.7 kB)
Downloading typing_inspection-0.4.2-py3-none-any.whl (14 kB)
Downloading anyio-4.14.2-py3-none-any.whl (125 kB)
Downloading mako-1.4.1-py3-none-any.whl (80 kB)
Downloading markupsafe-3.0.3-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (22 kB)
Downloading pyparsing-3.3.2-py3-none-any.whl (122 kB)
Building wheels for collected packages: video-channel-manager
  Building editable for video-channel-manager (pyproject.toml): started
  Building editable for video-channel-manager (pyproject.toml): finished with status 'done'
  Created wheel for video-channel-manager: filename=video_channel_manager-0.1.0-0.editable-py3-none-any.whl size=9476 sha256=1e6568ad4d52b8d5ae48fe53210df776b983fe7f90f33cfe8d866aa1f815257b
  Stored in directory: /tmp/pip-ephem-wheel-cache-tda315as/wheels/22/d8/cd/f5d0c5cea524da098d97505719d7a7fd41fbff8a6dfb242fc3
Successfully built video-channel-manager
Installing collected packages: sortedcontainers, boolean.py, urllib3, typing-extensions, tomli-w, tomli, tenacity, shellingham, ruff, python-dotenv, pyparsing, pygments, pluggy, platformdirs, pip-api, pathspec, packaging, packageurl-python, mypy_extensions, msgpack, mdurl, MarkupSafe, license-expression, librt, iniconfig, idna, h11, greenlet, filelock, defusedxml, coverage, charset_normalizer, certifi, annotated-types, annotated-doc, typing-inspection, sqlalchemy, requests, pytest, pydantic-core, py-serializable, pip-requirements-parser, mypy, markdown-it-py, Mako, httpcore, anyio, rich, pytest-cov, pydantic, httpx, cyclonedx-python-lib, CacheControl, alembic, typer, pydantic-settings, video-channel-manager, pip-audit

Successfully installed CacheControl-0.14.4 Mako-1.4.1 MarkupSafe-3.0.3 alembic-1.19.0 annotated-doc-0.0.5 annotated-types-0.8.0 anyio-4.14.2 boolean.py-5.0 certifi-2026.7.22 charset_normalizer-3.4.9 coverage-7.15.4 cyclonedx-python-lib-11.11.0 defusedxml-0.7.1 filelock-3.32.2 greenlet-3.5.4 h11-0.16.0 httpcore-1.0.9 httpx-0.28.1 idna-3.18 iniconfig-2.3.0 librt-0.15.0 license-expression-30.4.4 markdown-it-py-4.2.0 mdurl-0.1.2 msgpack-1.2.1 mypy-1.20.2 mypy_extensions-1.1.0 packageurl-python-0.17.6 packaging-26.3 pathspec-1.1.1 pip-api-0.0.34 pip-audit-2.10.1 pip-requirements-parser-32.0.1 platformdirs-4.11.1 pluggy-1.6.0 py-serializable-2.1.0 pydantic-2.13.4 pydantic-core-2.46.4 pydantic-settings-2.15.0 pygments-2.20.0 pyparsing-3.3.2 pytest-9.1.1 pytest-cov-7.1.0 python-dotenv-1.2.2 requests-2.34.2 rich-14.3.4 ruff-0.16.2 shellingham-1.5.4 sortedcontainers-2.4.0 sqlalchemy-2.0.51 tenacity-9.1.4 tomli-2.4.1 tomli-w-1.2.0 typer-0.27.1 typing-extensions-4.16.0 typing-inspection-0.4.2 urllib3-2.7.0 video-channel-manager-0.1.0
```

## edit
```text
Traceback (most recent call last):
  File "<stdin>", line 48, in <module>
KeyError: 'svodka-quiz-banana-botanical-berry'
```

## discovery
```text
{"discovered": true, "project_key": "svodka", "channel_username": "@deep_info_life", "chat_id": -1003527567039, "chat_username": "deep_info_life", "bot_id": 8716602202, "bot_username": "preaching_mp3_bot", "can_post_messages": true, "profile_sha256": "sha256:bbfd1a0b354a3ba874595a6397477498ba28f5dd5bdc2de298b1ef23649575d9"}
```

## format
```text
error: Failed to format tests/test_telegram_multichannel_release.py: No such file or directory (os error 2)
18 files left unchanged
```

## ruff
```text
E902 No such file or directory (os error 2)
--> tests/test_telegram_multichannel_release.py:1:1

Found 1 error.
```

## mypy
```text
src/video_channel_manager/telegram_channel_cli.py:165: error: Incompatible types in assignment (expression has type "SvodkaDraftPost | None", variable has type "SvodkaDraftPost")  [assignment]
Found 1 error in 1 file (checked 11 source files)
```

## pytest
```text
ERROR: file or directory not found: tests/test_telegram_multichannel_release.py


```

## candidate
```text
{"valid": true, "project_key": "svodka", "channel_username": "@deep_info_life", "profile_sha256": "sha256:bbfd1a0b354a3ba874595a6397477498ba28f5dd5bdc2de298b1ef23649575d9", "provider_writes_authorized": false}
{"valid": true, "count": 14, "format_counts": {"quick_fact": 7, "myth_fact": 3, "mini_digest": 1, "fresh_science": 1, "quiz": 2}, "queue_sha256": "sha256:8631ed1348145e1fde50862be5eabe3a7f1443ef5488af60919eb308f99b0521", "review_state": "draft_review_required", "provider_writes_authorized": false, "first_publication_id": "svodka-venus-day-longer-than-year", "last_publication_id": "svodka-dolphins-social-memory-whistles"}
{"built": true, "release_id": "svodka-pilot-2026-08-review-candidate", "release_digest": "sha256:7df3a71009b2f8942ff93f9a52ec10ea7e4f09f5b8c90f25ef48c7de8f356d65", "profile_sha256": "sha256:bbfd1a0b354a3ba874595a6397477498ba28f5dd5bdc2de298b1ef23649575d9", "target_binding_sha256": "sha256:aed54b5b2202706b6f50e56d73aacf9509479f405c028ca411cabcface890937", "chat_id": -1003527567039, "bot_id": 8716602202, "bot_username": "preaching_mp3_bot", "count": 14, "release_authorized": false, "output": "content/telegram/svodka/review-candidate-2026-08.json"}
candidate_digest=sha256:7df3a71009b2f8942ff93f9a52ec10ea7e4f09f5b8c90f25ef48c7de8f356d65
target_binding_digest=sha256:aed54b5b2202706b6f50e56d73aacf9509479f405c028ca411cabcface890937
```

