import sys
import os

# 현재 경로를 sys.path에 추가하여 app 모듈을 불러올 수 있게 함
sys.path.append(os.getcwd())

from app.core.i18n import get_text

def test_i18n():
    print("--- i18n Test ---")
    
    # 1. 한국어 테스트
    ko_text = get_text("chat.unlike.success", "ko")
    print(f"[KO] {ko_text}")
    assert "신고되었습니다" in ko_text

    # 2. 영어 테스트
    en_text = get_text("chat.unlike.success", "en")
    print(f"[EN] {en_text}")
    assert "reported" in en_text

    # 3. 일본어 테스트
    ja_text = get_text("chat.unlike.success", "ja")
    print(f"[JA] {ja_text}")
    assert "報告されました" in ja_text

    # 4. 변수 치환 테스트
    rejection_en = get_text("archive.rejection.content", "en", nickname="Alice", reason="Too short")
    print(f"[EN Rejection] {rejection_en}")
    assert "Alice" in rejection_en
    assert "Too short" in rejection_en

    # 5. 기본값(Fallback) 테스트
    fallback = get_text("non.existent.key", "en")
    print(f"[Fallback] {fallback}")
    assert fallback == "non.existent.key"

    print("\nAll i18n tests passed!")

if __name__ == "__main__":
    test_i18n()
