# =============================================================================
# 파일명: git_update.py
# 주기능: 깃허브 저장소와 로컬 프로젝트의 버전을 동기화/업데이트 하는 모듈
# =============================================================================

import os
import subprocess
import datetime

# ==========================================
# 사용자 설정 부분
# ==========================================

# 깃허브 프로젝트 최상위 경로 (git 명령어가 실행될 위치)
REPO_DIR = r"d:\Users\jarvis\source\repos\sunilc_home"

# ==========================================

def push_to_github():
    print("=== 홈페이지 파일 자동 업로드 스크립트 ===")
    
    # 깃허브 폴더가 존재하는지 확인
    if not os.path.exists(REPO_DIR):
        print(f"오류: 깃허브 프로젝트 폴더를 찾을 수 없습니다. ({REPO_DIR})")
        input("\n종료하려면 엔터키를 누르세요...")
        return

    print("\nGitHub로 파일 업로드를 시작합니다...")
    try:
        # git add .
        print("-> 변경된 파일 찾는 중...")
        subprocess.run(["git", "add", "."], cwd=REPO_DIR, check=True)
        
        # git commit
        # 변경 사항이 없을 경우를 대비해 오류를 무시하도록 처리
        time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"다운로드 파일 자동 업데이트 ({time_str})"
        result = subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, capture_output=True, text=True)
        
        if "nothing to commit" in result.stdout or "nothing added to commit" in result.stdout:
            print("-> 새로 추가되거나 변경된 파일이 없습니다. (업로드 생략)")
        else:
            # git push
            print("-> 서버로 전송 중... (잠시만 기다려주세요)")
            subprocess.run(["git", "push"], cwd=REPO_DIR, check=True)
            print("-> GitHub 업로드 완료! 약 1~2분 뒤 홈페이지가 갱신됩니다.")
            
    except subprocess.CalledProcessError as e:
        print(f"\n오류: Git 업로드 중 문제가 발생했습니다. Git이 설치되어 있는지 확인해주세요.")
    except FileNotFoundError:
         print(f"\n오류: 'git' 명령어를 찾을 수 없습니다. PC에 Git이 설치되어 있어야 합니다.")
    
    print("\n=== 모든 작업이 완료되었습니다 ===")
    input("창을 닫으려면 엔터키를 누르세요...")

if __name__ == "__main__":
    push_to_github()
