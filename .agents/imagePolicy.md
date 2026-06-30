# Crowdians: Image Storage & Caching Policy

본 문서는 Crowdians 메신저 플랫폼 내에서 에이전트(크루) 및 유저 아바타의 프로필 이미지를 저장, 최적화 및 서빙하기 위한 아키텍처 가이드라인입니다. 

실시간 대화방의 **극단적인 로딩 속도(Low Latency) 보장**과 온보딩 허들을 낮추는 **선택적 이미지 정책**을 달성하는 것을 목표로 합니다.

---

## 1. 이미지 규격 및 수량 정책 (Image Specification & Limits)

사용자가 올리는 이미지 리소스와 서버 트래픽 낭비를 막고, 회원 가입 시 이탈률을 0%에 수렴하게 만들기 위해 모든 이미지 등록은 **선택 사항(Optional)**으로 설계합니다.

### ① 프로필 및 감정 표현 세트 (Optional Max 6 Images)
에이전트나 유저 아바타가 저장 및 호출할 수 있는 이미지는 **최대 6장**으로 제한하며, 전부 등록하지 않아도 무방합니다.
*   `default`: 기본 프로필 (선택)
*   `happy`: 기쁨 상태 (선택)
*   `sad`: 슬픔 상태 (선택)
*   `angry`: 분노 상태 (선택)
*   `surprised`: 놀람 상태 (선택)
*   `blushed`: 부끄러움/설렘 상태 (선택)
*   
*   **폴백(Fallback) 규칙**:
    1.  특정 감정 이미지가 등록되어 있지 않거나 로드에 실패할 경우 ➡️ `default` 이미지로 폴백.
    2.  `default` 이미지조차 업로드하지 않은 경우 ➡️ **시스템 기본 제공 프로필 이미지(Default Placeholder)**로 최종 폴백.

### ② 업로드 제한 스펙 (아바타 이미지)
*   **지원 원본 포맷**: JPG, PNG, WEBP, GIF (정적인 1프레임만 추출)
*   **최대 파일 크기**: 파일당 **5 MB** 이하로 제한 (FastAPI 단에서 검증 및 거부)

### ③ 메시지 하단 일러스트 카드 스펙 (Illustration Cards)
*   **용도**: 대화 흐름 중 조건부로 하단에 동봉되는 대형 이미지 카드.
*   **지원 원본 포맷**: JPG, PNG, WEBP, GIF
*   **최대 파일 크기**: 파일당 **10 MB** 이하로 제한 (FastAPI 단에서 검증 및 거부)

---

## 2. 이미지 처리 파이프라인 (Image Processing Pipeline)

사용자가 선택적으로 올린 원본 이미지는 대화 화면에 직접 송출되지 않고, 백엔드에서 강제적인 압축 및 규격 최적화 단계를 거칩니다.

### ① 아바타 이미지 처리
```
[원본 아바타 업로드 (최대 5MB)] ──► [FastAPI 백엔드 (Pillow)] ──► 1. 256x256 픽셀 리사이징 (LANCZOS)
                                                               2. WebP 포맷 인코딩 (퀄리티 82%)
                                                               ──► [GCS 버킷 업로드 (약 25 KB)]
```

### ② 메시지 하단 일러스트 이미지 처리
```
[원본 일러스트 업로드 (최대 10MB)] ──► [FastAPI 백엔드 (Pillow)] ──► 1. 최대 800x800 해상도 리사이징 (비율 유지)
                                                                 2. WebP 포맷 인코딩 (퀄리티 80%)
                                                                 ──► [GCS 버킷 업로드 (약 100~150 KB)]
```

### Pillow 최적화 파이프라인 (Python 예시)
```python
from PIL import Image
import io

def optimize_avatar_image(raw_image_bytes: bytes) -> bytes:
    image = Image.open(io.BytesIO(raw_image_bytes))
    
    # 투명도(Alpha) 보존을 위해 RGBA 변환
    if image.mode != "RGBA":
        image = image.convert("RGBA")
        
    # 가로세로 비율 유지하며 256x256 크기로 리사이징
    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    
    output = io.BytesIO()
    # WebP 압축 및 손실률을 조절하여 20-30KB 내외로 가볍게 압축
    image.save(output, format="WEBP", quality=82, method=6)
    return output.getvalue()

def optimize_illustration_image(raw_image_bytes: bytes) -> bytes:
    image = Image.open(io.BytesIO(raw_image_bytes))
    
    if image.mode != "RGBA":
        image = image.convert("RGBA")
        
    # 최대 800x800 해상도로 비율을 유지하며 썸네일 리사이징
    max_size = (800, 800)
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    output = io.BytesIO()
    # 대형 이미지이므로 퀄리티 80%로 타협하여 파일 크기 최적화 (100KB 내외)
    image.save(output, format="WEBP", quality=80, method=6)
    return output.getvalue()
```

---

## 3. 캐싱 및 전송 최적화 (Caching & Egress Optimization)

GCP의 아시아 리전 기준 아웃바운드 네트워크 트래픽 비용(Egress)은 상대적으로 비싸므로, 클라이언트 캐싱을 극대화하여 비용을 방어합니다.

### ① HTTP 캐싱 헤더 정책
GCS 버킷에서 이미지를 반환할 때, 혹은 Cloud CDN을 거쳐 나갈 때 아래의 캐시 헤더를 강제 적용합니다.
```http
Cache-Control: public, max-age=31536000, immutable
```
*   **`immutable`**: 이미지가 로드된 후 유저가 새로고침을 하더라도 브라우저가 서버에 "변경 사항이 있는지" 묻지 않고 로컬 캐시를 100% 신뢰하여 즉시 렌더링하게 만듭니다.
*   **버전 관리 (Cache Busting)**: 이미지를 교체할 경우, 파일명을 덮어쓰지 않고 새로운 UUID나 해시를 쿼리 파라미터로 추가(`avatar.webp?v=hash123`)하여 캐시를 강제 갱신시킵니다.

### ② 클라이언트 사이드 프리로딩 & 렌더링 최적화

#### 1. 감정별 아바타 이미지 프리로드 (Avatar Preloading)
*   사용자가 채팅방에 진입하는 즉시, 해당 방 참여 에이전트들 중 감정 이미지가 존재하여 프리로드가 가능한 대상에 한해 6가지 감정 아바타 이미지 URL들을 백그라운드에서 캐시합니다.
*   이미지가 등록되지 않은 경우는 별도 네트워크 요청 없이 시스템 로컬 기본 아바타로 대응하여 불필요한 HTTP 전송 실패 비용을 절약합니다.

#### 2. 일러스트 카드 렌더링과 레이아웃 팽창 방지 (Layout Shift Prevention)
*   **고정 비율 컨테이너 확보**: `has_illustration` 속성이 `True`인 메시지는 일러스트 카드가 화면에 보이기 전, CSS `aspect-ratio` 속성을 이용하여 영역을 미리 잡고 있어 이미지 다운로드가 완료되어도 전체 스크롤 위치가 흔들리지 않도록 예방합니다.
*   **스케줄러와 스케일 제어**: 이미지 로딩 중에는 스켈레톤(Skeleton UI)을 표시하여 레이아웃 팽창을 방지합니다. 

---

## 4. 인프라 비용 예측 시뮬레이션 (Cost Simulation)

*   **가정**: 활성 에이전트 10,000개 (감정 이미지는 약 30%만 선택 등록했다고 가정, 나머지 기본 프로필 공유), 월간 대화방 내 이미지 노출(조회) 수 10,000,000회.

| 항목 | 계산 수식 | 월 예상 비용 | 비고 |
| :--- | :--- | :--- | :--- |
| **저장 비용 (GCS Standard)** | 등록된 이미지 18,000장 × 25 KB = 450 MB <br> 450 MB × $0.02/GB | **$0.01 / 월** | 무시할 수 있는 수준 |
| **현실적인 전송 비용 (캐싱 95% 작동)** | 실제 서버 트래픽 6 GB 발생 <br> 6 GB × $0.08/GB | **$0.48 / 월** | 대다수 기본 프로필 및 브라우저 로컬 캐시 활용 |
| **Cloud CDN 작동 비용** | Cache Hit 트래픽 비용 | **$0.25 / 월** | 대역폭 비용 추가 절감 효과 |

*   **최종 예상 비용**: **월 $1.0 내외**

---

## 5. 이미지 안전성 필터링 (Safety Moderation)

*   **솔루션**: **GCP Cloud Vision API (SafeSearch Detection)**
*   **적용 대상**: 기본 제공 프로필 외에 유저 및 크리에이터가 **선택적으로 업로드한 아바타 및 일러스트 이미지 전체**.
*   **필터링 임계치**: `adult`, `violence`, `racy` 항목 판별 신뢰도가 `LIKELY` (4) 이상인 경우 즉시 거부 후 파일 영구 저장 취소.
