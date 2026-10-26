import pandas as pd
import requests
import streamlit as st

# 페이지 설정 (반응형 레이아웃)
st.set_page_config(
    page_title="내노예 - CSO 영업 관리 시스템",
    page_icon="💊",
    layout="wide",
)

# 모던하고 깔끔한 UI CSS
st.markdown(
    """
    <style>
    .main { background-color: #f8f9fa; }
    h1 { color: #1e293b; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)

# 세션 상태 초기화 (데이터 가상 저장용)
if "sales_data" not in st.session_state:
    st.session_state["sales_data"] = pd.DataFrame(
        columns=[
            "거래처",
            "품목명",
            "기준월",
            "전월매출",
            "당월매출",
            "생동여부",
            "자사생산여부",
            "요율(%)",
        ]
    )

if "shortage_data" not in st.session_state:
    st.session_state["shortage_data"] = pd.DataFrame(
        columns=["품목명", "품절상태", "해소예정일", "비고"]
    )

if "rate_table" not in st.session_state:
    st.session_state["rate_table"] = pd.DataFrame(
        columns=["품목코드", "품목명", "제조사", "생동여부", "자사생산", "요율(%)"]
    )

if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

if "api_endpoint" not in st.session_state:
    st.session_state["api_endpoint"] = (
        "https://apis.data.go.kr/1471000/DrugPrdInfoService03/getDrugPrdInfo03"
    )

# 타이틀
st.title("💊 내노예: CSO 의약품 영업 관리")
st.markdown("---")

# 📌 상단 탭 메뉴
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "📊 매출 입력·비교",
        "📈 총매출 트렌드",
        "🚨 품절 매칭·팔로업",
        "💡 대체 품목 추천",
        "📂 요율표 갱신",
        "⚙️ API 설정 및 실시간 조회",
    ]
)


# ==========================================
# 1. 매출 입력 및 비교 관리
# ==========================================
with tab1:
    st.header("📊 매출 입력 및 전월 대비 증감 비교")

    with st.form("sales_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            client = st.text_input("거래처명 (의원)")
            item = st.text_input("품목명")
            target_month = st.text_input("기준월 (예: 2026-10)", "2026-10")
        with col2:
            prev_sales = st.number_input(
                "전월 매출액 (원)", min_value=0, step=10000, format="%d"
            )
            curr_sales = st.number_input(
                "당월 매출액 (원)", min_value=0, step=10000, format="%d"
            )
            col_sub1, col_sub2 = st.columns(2)
            with col_sub1:
                is_bio = st.selectbox("생동 여부", ["해당", "미해당"])
            with col_sub2:
                is_self = st.selectbox("자사 생산", ["자사", "위탁"])

        submitted = st.form_submit_button(
            "➕ 매출 데이터 등록", use_container_width=True
        )
        if submitted and client and item:
            new_row = pd.DataFrame(
                {
                    "거래처": [client],
                    "품목명": [item],
                    "기준월": [target_month],
                    "전월매출": [prev_sales],
                    "당월매출": [curr_sales],
                    "생동여부": [is_bio],
                    "자사생산여부": [is_self],
                    "요율(%)": [0.0],
                }
            )
            st.session_state["sales_data"] = pd.concat(
                [st.session_state["sales_data"], new_row], ignore_index=True
            )
            st.success(f"[{client}] {item} 매출 데이터가 등록되었습니다.")

    st.markdown("### 📋 등록된 매출 증감 현황")
    if not st.session_state["sales_data"].empty:
        df = st.session_state["sales_data"].copy()
        df["증감액"] = df["당월매출"] - df["전월매출"]

        def color_change(val):
            if val > 0:
                return "color: #2563eb; font-weight: bold;"
            elif val < 0:
                return "color: #dc2626; font-weight: bold;"
            else:
                return "color: #111827;"

        styled_df = df.style.map(color_change, subset=["증감액"]).format(
            {
                "전월매출": "{:,} 원",
                "당월매출": "{:,} 원",
                "증감액": "{:,} 원",
            }
        )
        st.dataframe(styled_df, use_container_width=True)
    else:
        st.info("등록된 매출 데이터가 없습니다. 위 폼을 통해 입력해주세요.")


# ==========================================
# 2. 거래처별 총매출 트렌드
# ==========================================
with tab2:
    st.header("📈 거래처별 총매출 트렌드 요약")

    if not st.session_state["sales_data"].empty:
        df = st.session_state["sales_data"]
        summary = (
            df.groupby(["거래처", "기준월"])[["전월매출", "당월매출"]]
            .sum()
            .reset_index()
        )
        summary["증감액"] = summary["당월매출"] - summary["전월매출"]

        st.dataframe(summary, use_container_width=True)

        selected_client = st.selectbox(
            "상세 트렌드를 볼 거래처 선택", df["거래처"].unique(), key="trend_client"
        )
        client_df = df[df["거래처"] == selected_client]
        st.bar_chart(client_df.set_index("품목명")["당월매출"])
    else:
        st.info("요약할 매출 데이터가 없습니다.")


# ==========================================
# 3. 품절 품목 매칭 및 팔로업
# ==========================================
with tab3:
    st.header("🚨 품절 품목 등록 및 거래처 매칭 팔로업")

    with st.form("shortage_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            s_item = st.text_input("품절/중단 품목명")
            s_status = st.selectbox(
                "상태", ["일시품절", "장기품절(2달 이상)", "제품중단"]
            )
        with col2:
            s_date = st.text_input("해소 예정일 (또는 '미정')", "2026-11-30")
            s_memo = st.text_input("팔로업 메모")

        s_submitted = st.form_submit_button(
            "➕ 품절 공지 등록", use_container_width=True
        )
        if s_submitted and s_item:
            new_s = pd.DataFrame(
                {
                    "품목명": [s_item],
                    "품절상태": [s_status],
                    "해소예정일": [s_date],
                    "비고": [s_memo],
                }
            )
            st.session_state["shortage_data"] = pd.concat(
                [st.session_state["shortage_data"], new_s], ignore_index=True
            )
            st.success(f"[{s_item}] 품절 정보가 등록되었습니다.")

    st.markdown("### 🔗 거래처 처방 품목 중 품절 매칭 현황")
    if not st.session_state["sales_data"].empty and not st.session_state["shortage_data"].empty:
        sales_df = st.session_state["sales_data"]
        short_df = st.session_state["shortage_data"]

        matched = pd.merge(sales_df, short_df, on="품목명", how="inner")
        if not matched.empty:
            st.warning(
                "현재 거래처에서 처방 중인 품목 중 품절/중단된 항목이 있습니다!"
            )
            st.dataframe(
                matched[
                    [
                        "거래처",
                        "품목명",
                        "기준월",
                        "품절상태",
                        "해소예정일",
                        "비고",
                    ]
                ],
                use_container_width=True,
            )
        else:
            st.success(
                "현재 거래처 처방 품목 중 품절 공지와 일치하는 항목이 없습니다."
            )
    else:
        st.info("매출 데이터와 품절 데이터를 모두 입력해야 매칭 결과를 볼 수 있습니다.")


# ==========================================
# 4. 대체 품목 추천 (장기품절/중단)
# ==========================================
with tab4:
    st.header("💡 장기품절·중단 품목 대체 추천")
    st.markdown(
        "요율표 기준 **최고 요율 + 생동 + 자사 생산** 조건을 만족하는 대체 품목을 추천합니다."
    )

    if not st.session_state["shortage_data"].empty and not st.session_state["rate_table"].empty:
        long_term_shortages = st.session_state["shortage_data"][
            st.session_state["shortage_data"]["품절상태"].isin(
                ["장기품절(2달 이상)", "제품중단"]
            )
        ]

        if not long_term_shortages.empty:
            st.write("📌 **대체 추천이 필요한 품목 리스트:**")
            st.dataframe(long_term_shortages, use_container_width=True)

            rate_df = st.session_state["rate_table"]

            st.subheader("🌟 AI 추천 대체 품목 (생동 · 자사생산 · 고요율 순)")
            recommended = rate_df[
                (rate_df["생동여부"] == "해당")
                & (rate_df["자사생산"] == "자사")
            ].sort_values(by="요율(%)", ascending=False)

            if not recommended.empty:
                st.dataframe(recommended, use_container_width=True)
                top_pick = recommended.iloc[0]
                st.success(
                    f"🏆 **추천 1순위**: [{top_pick['제조사']} - {top_pick['품목명']} / 요율: {top_pick['요율(%)']}%]"
                )
            else:
                st.warning(
                    "조건(생동·자사생산)을 만족하는 요율표 데이터가 없습니다. 5번 메뉴를 확인해주세요."
                )
        else:
            st.info(
                "현재 장기품절(2개월 이상) 또는 제품중단 상태인 품목이 없습니다."
            )
    else:
        st.info("품절 정보와 요율표(5번 메뉴)가 먼저 등록되어 있어야 합니다.")


# ==========================================
# 5. 월별 요율표 갱신 (Excel)
# ==========================================
with tab5:
    st.header("📂 월별 요율표 엑셀 업로드 및 필터")

    uploaded_file = st.file_uploader("요율표 엑셀 파일 업로드", type=["xlsx", "xls"])
    if uploaded_file is not None:
        df_rate = pd.read_excel(uploaded_file)
        st.session_state["rate_table"] = df_rate
        st.success("요율표가 성공적으로 갱신되었습니다!")

    if not st.session_state["rate_table"].empty:
        st.subheader("📋 등록된 요율표 데이터 및 필터")
        df_r = st.session_state["rate_table"]

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if "생동여부" in df_r.columns:
                f_bio = st.multiselect(
                    "생동여부 필터",
                    df_r["생동여부"].unique(),
                    default=df_r["생동여부"].unique(),
                )
                df_r = df_r[df_r["생동여부"].isin(f_bio)]
        with col_f2:
            if "자사생산" in df_r.columns:
                f_self = st.multiselect(
                    "자사생산 필터",
                    df_r["자사생산"].unique(),
                    default=df_r["자사생산"].unique(),
                )
                df_r = df_r[df_r["자사생산"].isin(f_self)]

        st.dataframe(df_r, use_container_width=True)
    else:
        st.info("등록된 요율표가 없습니다. 엑셀 파일을 업로드해주세요.")


# ==========================================
# 6. API 설정 및 실시간 조회 페이지
# ==========================================
with tab6:
    st.header("⚙️ 공공보건 데이터 및 외부 API 연동 & 실시간 조회")

    with st.form("api_form"):
        api_key_input = st.text_input(
            "공공보건 데이터 API Key 입력",
            value=st.session_state["api_key"],
            type="password",
        )
        api_endpoint_input = st.text_input(
            "API Base URL", value=st.session_state["api_endpoint"]
        )
        api_saved = st.form_submit_button(
            "API 설정 저장", use_container_width=True
        )

        if api_saved:
            st.session_state["api_key"] = api_key_input.strip()
            st.session_state["api_endpoint"] = api_endpoint_input.strip()
            st.success("API 키 및 설정이 안전하게 저장되었습니다.")

    st.markdown("---")
    st.subheader("🔍 실시간 공공 의약품 데이터 조회")

    if not st.session_state["api_key"]:
        st.warning(
            "⚠️ 먼저 위에서 API Key를 입력하고 저장해 주세요. (인증키 필요)"
        )
    else:
        search_drug = st.text_input(
            "검색할 의약품명 (예: 타이레놀, 아목시실린 등)"
        )
        if st.button("🚀 실시간 공공 데이터 조회하기", use_container_width=True):
            if not search_drug:
                st.error("검색할 의약품명을 입력해주세요.")
            else:
                with st.spinner("공공데이터 포털에서 정보를 불러오는 중..."):
                    try:
                        # 이중 인코딩 방지를 위해 서비스키를 URL에 직접 안전하게 결합
                        target_url = f"{st.session_state['api_endpoint']}?serviceKey={st.session_state['api_key']}&type=json&numOfRows=10&pageNo=1&itemName={search_drug}"

                        response = requests.get(target_url, timeout=7)

                        if response.status_code == 200:
                            try:
                                res_json = response.json()
                                items = (
                                    res_json.get("response", {})
                                    .get("body", {})
                                    .get("items", [])
                                )
                                if isinstance(items, dict):
                                    items = items.get("item", [])

                                if items:
                                    df_api = pd.DataFrame(items)
                                    st.success(
                                        f"'{search_drug}' 검색 결과 총 {len(df_api)}건을 불러왔습니다!"
                                    )
                                    st.dataframe(df_api, use_container_width=True)
                                else:
                                    st.info(
                                        "검색된 의약품 데이터가 없습니다. (입력하신 의약품명이 정확한지 확인해주세요)"
                                    )
                                    st.json(res_json)
                            except Exception as json_err:
                                st.error(
                                    f"데이터 파싱 중 오류가 발생했습니다: {json_err}"
                                )
                                st.text(response.text[:500])
                        else:
                            st.error(
                                f"API 호출 실패 (상태 코드: {response.status_code}). 인증키나 엔드포인트 주소를 확인해주세요."
                            )
                    except Exception as e:
                        st.error(
                            f"통신 중 오류가 발생했습니다 (네트워크 또는 URL 확인): {e}"
                        )