import streamlit as st
import pandas as pd
import altair as alt

import requests
import time
from datetime import datetime, timedelta

message_1 = r"""
嗨，我是Archer👋

這是一個台股每日交易資料流程自動化的資料工程展示作品，內容僅供參考。\
請點擊上方 :red[HOME] 右邊的 :blue[STOCK] 頁籤查看使用。

＊該應用非為即時資料顯示，每日交易資料在交易日14:40更新後顯示，請稍等後重新整理畫面。
"""
message_flow = """
A. 資料來源為TWSE臺灣證券交易所，使用技術工具包含如下：

    1. Azure Functions (free tier)
    2. Azure Database for PostgreSQL (free tier)
    3. LINE Notify
    4. Streamlit (Streamlit Community Cloud)
    5. GitHub

B. 作業流程主要分為以下2個部分：

    1. 每日交易資料收集流程

        a. 於 Azure Functions 執行
        b. Azure Functions 每日排程函數，將於 14:40 呼叫 TWSE API 取得每日交易資料
        c. 將資料處理後存入至 Azure Database for PostgreSQL 資料庫中
        d. 呼叫 LINE Notify 通知資料收集結果 (成功或失敗)
        e. 資料收集流程結束

    2. 網頁資料視覺化呈現

        a. 於 Streamlit Community Cloud 執行 (位於美國)
        b. 使用者在 STOCK 頁籤
        c. 呼叫 Azure Functions API函數取得所有股票
        d. 使用者選取欲查看之股票
        e. 呼叫 Azure Functions API函數取得該股票所有交易資料
        f. 以各種呈現方式顯示資料
"""
message_2 = """
感謝您撥冗閱覽，祝您有愉快的一天🤗
"""

STOCK_LIST_API = "https://archer-twse-functions.azurewebsites.net/api/get_stock_list?"

STOCK_DAILY_API = (
    "https://archer-twse-functions.azurewebsites.net/api/http_trigger?stock={stock}"
)


def stream_data(message: str):
    for word in message.split(" "):
        yield word + " "
        time.sleep(0.03)


def get_ttl():
    now = datetime.now()
    next_time_1440 = now.replace(hour=6, minute=40, second=59, microsecond=0)
    if now > next_time_1440:
        next_time_1440 += timedelta(days=1)
    return next_time_1440 - now


@st.cache_data(ttl=get_ttl())
def get_stock_list() -> list:
    """取得股票清單"""
    try:
        response = requests.post(STOCK_LIST_API)
        response.raise_for_status()
        stock_list = [" ".join(stock.values()) for stock in response.json()]
        return stock_list
    except requests.RequestException as e:
        st.error(f"Error fetching stock list: {e}")
        return []


@st.cache_data(ttl=get_ttl())
def get_stock_daily_price(stock: str) -> pd.DataFrame:
    """取得個股每日交易資訊"""
    try:
        response = requests.post(STOCK_DAILY_API.format(stock=stock))
        response.raise_for_status()
        stock_daily_data = response.json()
        return _clean_data_and_to_df(stock_daily_data)
    except requests.RequestException as e:
        st.error(f"Error fetching daily stock price: {e}")
        return pd.DataFrame()


def _clean_data_and_to_df(stock_daily) -> pd.DataFrame:
    """清理資料並轉為DataFrame"""
    stock_daily_df = (
        pd.DataFrame(stock_daily)
        .replace("None", pd.NA)
        .dropna()
        .assign(trade_date=lambda df: pd.to_datetime(df["trade_date"]))
    )

    filter_col = [
        "opening_price",
        "highest_price",
        "lowest_price",
        "closing_price",
    ]
    stock_daily_df = stock_daily_df[
        ~(stock_daily_df[filter_col] == "$0.00").any(axis=1)
    ]

    columns_to_float = [
        "trade_value",
        "opening_price",
        "highest_price",
        "lowest_price",
        "closing_price",
        "change",
    ]
    stock_daily_df[columns_to_float] = (
        stock_daily_df[columns_to_float].replace({"[$,]": ""}, regex=True).astype(float)
    )
    columns_to_int = [
        "trade_volume",
        "transaction",
    ]
    stock_daily_df[columns_to_int] = stock_daily_df[columns_to_int].astype(int)
    return stock_daily_df


@st.experimental_fragment
def fragment_stock() -> None:
    """根據選項獨立重新運作區塊"""

    start_time = datetime.now()

    selectbox_options = get_stock_list()
    selected_stock = st.selectbox(
        "Stock", options=selectbox_options, placeholder="Select Stock..."
    )
    if selected_stock:
        stock = dict(zip(["code", "name"], selected_stock.split(" ")))
        stock_daily_df = get_stock_daily_price(stock.get("code"))

        if not stock_daily_df.empty:
            display_stock_info(stock_daily_df, stock)

    end_time = datetime.now()
    st.toast(f"Finished in {(end_time-start_time).total_seconds()} s", icon="✅")


def display_stock_info(stock_daily_df, stock) -> None:
    """Display the stock information in the Streamlit app."""
    today_data = stock_daily_df.iloc[-1]
    yesterday_data = stock_daily_df.iloc[-2]

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "日期", today_data["trade_date"].strftime("%Y/%m/%d"), delta_color="off"
    )
    col2.metric(
        "股價", today_data["closing_price"], today_data["change"], delta_color="inverse"
    )
    col3.metric(
        "成交量(股)",
        f'{int(today_data["trade_volume"]):,}',
        f'{int(today_data["trade_volume"]) - int(yesterday_data["trade_volume"]):,}',
        delta_color="inverse",
    )

    input_date_long = 7
    date_long = min(stock_daily_df.shape[0], input_date_long)
    df_long_data = stock_daily_df.iloc[-1 : -date_long - 1 : -1].copy()
    df_long_data["trade_date"] = df_long_data["trade_date"].apply(
        lambda d: d.date().strftime("%Y-%m-%d")
    )
    df_long_data["code"] = stock["code"]
    df_long_data["name"] = stock["name"]

    st.dataframe(
        df_long_data[
            [
                "trade_date",
                "code",
                "name",
                "opening_price",
                "highest_price",
                "lowest_price",
                "closing_price",
                "trade_volume",
            ]
        ],
        column_config={
            "trade_date": st.column_config.TextColumn("交易日期"),
            "code": st.column_config.TextColumn("代號"),
            "name": st.column_config.TextColumn("名稱"),
            "opening_price": st.column_config.NumberColumn("開盤價"),
            "highest_price": st.column_config.NumberColumn("最高價"),
            "lowest_price": st.column_config.NumberColumn("最低價"),
            "closing_price": st.column_config.NumberColumn("收盤價"),
            "trade_volume": st.column_config.NumberColumn("成交量(股)"),
        },
        hide_index=True,
        use_container_width=True,
    )

    df_line = pd.DataFrame(
        {
            "views_history_7": [
                stock_daily_df["closing_price"].tail(7).values.tolist()
            ],
            "views_history_30": [
                stock_daily_df["closing_price"].tail(30).values.tolist()
            ],
            "views_history_365": [
                stock_daily_df["closing_price"].tail(365).values.tolist()
            ],
        }
    )

    st.dataframe(
        df_line,
        column_config={
            "views_history_7": st.column_config.LineChartColumn(
                "週趨勢",
                y_min=float(min(df_line["views_history_7"].values[0])),
                y_max=float(max(df_line["views_history_7"].values[0])),
            ),
            "views_history_30": st.column_config.LineChartColumn(
                "月趨勢",
                y_min=float(min(df_line["views_history_30"].values[0])),
                y_max=float(max(df_line["views_history_30"].values[0])),
            ),
            "views_history_365": st.column_config.LineChartColumn(
                "年趨勢",
                y_min=float(min(df_line["views_history_365"].values[0])),
                y_max=float(max(df_line["views_history_365"].values[0])),
            ),
        },
        hide_index=True,
        use_container_width=True,
    )

    cp_chart = (
        alt.Chart(stock_daily_df)
        .mark_line(clip=True)
        .encode(
            alt.X("trade_date").title("交易日期"), alt.Y("closing_price").title("股價")
        )
        .interactive(bind_y=False)
    )
    st.altair_chart(cp_chart, theme="streamlit", use_container_width=True)

    tv_chart = (
        alt.Chart(stock_daily_df)
        .mark_line(clip=True)
        .encode(
            alt.X("trade_date").title("交易日期"),
            alt.Y("trade_volume").title("成交量(股)"),
        )
        .interactive(bind_y=False)
    )
    st.altair_chart(tv_chart, theme="streamlit", use_container_width=True)


def main():
    st.title("Archer TWSE Demo")
    st.info("[2024.07.09]最近更新: 優化資料載入及 UI 體驗，減少等待時間。 ", icon="ℹ️")
    tab1, tab2 = st.tabs(["HOME", "STOCK"])
    with tab1:
        st.subheader("Hello")
        st.write_stream(stream_data(message_1))

        st.subheader("Tools and Flows")
        st.image("streamlit_app/flow.png", caption="流程架構")
        st.write_stream(stream_data(message_flow))
        st.write_stream(stream_data(message_2))

        st.subheader("Screenshot")
        (
            col1,
            col2,
        ) = st.columns(
            spec=[0.7, 0.3],
            vertical_alignment="center",
        )
        with col1:
            st.image("streamlit_app/stock.jpg", caption="STOCK")
        with col2:
            st.image("streamlit_app/line_notify.jpg", caption="LINE Notify")
        st.image("streamlit_app/azure.jpg", caption="Azure")

    with tab2:
        fragment_stock()


if __name__ == "__main__":
    main()
