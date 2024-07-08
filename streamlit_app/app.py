import streamlit as st
import pandas as pd
import altair as alt

import requests
import json
import time


message_1 = r"""
嗨，我是Archer👋

這是一個台股每日交易資料流程自動化的資料工程展示作品，內容僅供參考。\
請點擊上方 :red[HOME] 右邊的 :blue[STOCK] 頁籤查看使用。

＊該應用非為即時資料顯示，每日交易資料在交易日14:30更新後顯示，請稍等後重新整理畫面。
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
        b. Azure Functions 每日排程函數，將於 14:30 呼叫 TWSE API 取得每日交易資料
        c. 將資料處理後存入至 Azure Database for PostgreSQL 資料庫中
        d. 呼叫 LINE Notify 通知資料收集結果 (成功或失敗)
        e. 資料收集流程結束

    2. 網頁資料視覺化呈現

        a. 於 Streamlit Community Cloud 執行 (位於美國，可能需要一些時間等待一下)
        b. 使用者在 STOCK 頁籤
        c. 呼叫 Azure Functions API函數取得所有股票
        d. 使用者選取欲查看之股票
        e. 呼叫 Azure Functions API函數取得該股票所有交易資料
        f. 以各種呈現方式顯示資料
"""
message_2 = """
感謝您撥冗閱覽，祝您有愉快的一天🤗
"""

get_stock_list_api = (
    "https://archer-twse-functions.azurewebsites.net/api/get_stock_list?"
)

get_stock_daily_api = (
    "https://archer-twse-functions.azurewebsites.net/api/http_trigger?stock={stock}"
)


def get_stock_daily_price(stock: str):
    response = requests.post(get_stock_daily_api.format(stock=stock))
    return json.loads(response.text)


def get_stock_list():
    response = requests.post(get_stock_list_api)
    return json.loads(response.text)


def stream_data(message: str):
    for word in message.split(" "):
        yield word + " "
        time.sleep(0.03)


def main():
    #
    stock_list = get_stock_list()
    selectbox_options = [" ".join(stock.values()) for stock in stock_list]

    #
    st.title("Archer TWSE Demo")
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
        seleted_stock = st.selectbox(
            "Stock",
            options=selectbox_options,
            index=None,
            placeholder="Select Stock...",
        )

        if seleted_stock:
            seleted_stock = dict(zip(["code", "name"], seleted_stock.split(" ")))
            stock_daily = get_stock_daily_price(seleted_stock.get("code"))

            # data load and process
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
                stock_daily_df[columns_to_float]
                .replace({"[$,]": ""}, regex=True)
                .astype(float)
            )
            columns_to_int = [
                "trade_volume",
                "transaction",
            ]
            stock_daily_df[columns_to_int] = stock_daily_df[columns_to_int].astype(int)

            # 最後交易日簡易資訊
            today_data = stock_daily_df.iloc[-1]
            yesterday_data = stock_daily_df.iloc[-2]
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "日期",
                today_data["trade_date"].strftime("%Y/%m/%d"),
                delta_color="off",
            )
            col2.metric(
                "股價",
                today_data["closing_price"],
                today_data["change"],
                delta_color="inverse",
            )
            col3.metric(
                "成交量(股)",
                f'{int(today_data["trade_volume"]):,}',
                f'{int(today_data["trade_volume"])-int(yesterday_data["trade_volume"]):,}',
                delta_color="inverse",
            )

            # 近一週資訊表格
            date_long = min(stock_daily_df.shape[0], 7)
            df_long_data = pd.DataFrame(
                {
                    "trade_date": stock_daily_df.loc[
                        stock_daily_df.index[-1 : date_long * (-1) - 1 : -1],
                        "trade_date",
                    ].apply(lambda d: str(d.date())),
                    "code": [seleted_stock.get("code")] * date_long,
                    "name": [seleted_stock.get("name")] * date_long,
                    "opening_price": stock_daily_df.loc[
                        stock_daily_df.index[-1 : date_long * (-1) - 1 : -1],
                        "opening_price",
                    ],
                    "highest_price": stock_daily_df.loc[
                        stock_daily_df.index[-1 : date_long * (-1) - 1 : -1],
                        "highest_price",
                    ],
                    "lowest_price": stock_daily_df.loc[
                        stock_daily_df.index[-1 : date_long * (-1) - 1 : -1],
                        "lowest_price",
                    ],
                    "closing_price": stock_daily_df.loc[
                        stock_daily_df.index[-1 : date_long * (-1) - 1 : -1],
                        "closing_price",
                    ],
                    "trade_volume": stock_daily_df.loc[
                        stock_daily_df.index[-1 : date_long * (-1) - 1 : -1],
                        "trade_volume",
                    ],
                }
            )
            st.dataframe(
                df_long_data,
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

            # 週月年趨勢
            df_line = pd.DataFrame(
                {
                    "views_history_7": [
                        stock_daily_df.loc[
                            stock_daily_df.index[-7:], "closing_price"
                        ].T.values.tolist()
                    ],
                    "views_history_30": [
                        stock_daily_df.loc[
                            stock_daily_df.index[-30:], "closing_price"
                        ].T.values.tolist()
                    ],
                    "views_history_365": [
                        stock_daily_df.loc[
                            stock_daily_df.index[-365:], "closing_price"
                        ].T.values.tolist()
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

            # 歷史趨勢
            cp_chart = (
                alt.Chart(stock_daily_df)
                .mark_line(clip=True)
                .encode(
                    alt.X("trade_date").title("交易日期"),
                    alt.Y("closing_price").title("股價"),
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


if __name__ == "__main__":
    main()
