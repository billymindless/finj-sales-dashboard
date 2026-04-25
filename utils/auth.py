import streamlit as st


def get_password() -> str:
    """설정된 비밀번호 반환 (secrets 없으면 기본값)"""
    try:
        return st.secrets["password"]
    except Exception:
        return "finj2024"


def login_page():
    """로그인 UI 렌더링, 인증 성공 시 True 반환"""
    st.markdown(
        """
        <style>
        .login-container { max-width: 420px; margin: 80px auto; }
        .login-title { font-size: 2rem; font-weight: 700; text-align: center; margin-bottom: 0.2rem; }
        .login-sub { text-align: center; color: #64748B; margin-bottom: 2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-title">📊 핀즈 대시보드</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">FINJ Sales Dashboard</div>', unsafe_allow_html=True)
        st.markdown("---")

        password = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        if st.button("로그인", use_container_width=True, type="primary"):
            if password == get_password():
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")


def require_auth():
    """인증 확인 - 미인증 시 로그인 페이지 렌더링 후 실행 중단"""
    if not st.session_state.get("authenticated"):
        login_page()
        st.stop()
