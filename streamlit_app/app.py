import streamlit as st
import pandas as pd
import altair as alt

import requests
import json
import time

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
        time.sleep(0.02)


def main():
    tab1, tab2 = st.tabs(["HOME", "STOCK"])
    with tab1:
        message = """
        🤗嗨，我是Archer，
        這是我的台股每日交易資料工程展示作品，內容僅供參考。
        備註：部分交易歷史資料尚不完整，每日交易資料將在交易日(?)下午兩點更新，請稍等後重新整理畫面。
        感謝您撥冗閱覽，祝您有愉快的一天。
        
        🤗Hello, I'm Archer.
        This is my TWSE daily trading data engineering demo, for reference only.
        Note: Some historical trading data might be incomplete. The daily trading data will be updated at 2:00 PM on each trading day. Please wait and refresh the screen.
        Thank you for your time and have a great day.
        """
        st.write_stream(stream_data(message))
        st.write("流程架構")
        st.image("streamlit_app/flow.png", caption="flow")
    with tab2:
        stock_list = get_stock_list()
        options = {" ".join(stock.values()): stock["code"] for stock in stock_list}

        st.title("TWSE demo")
        seleted_stock = st.selectbox(
            "Stock",
            options=options.keys(),
            index=None,
            placeholder="Select Stock...",
        )

        if seleted_stock:
            stock_daily = get_stock_daily_price(options[seleted_stock])
            stock_daily_df = pd.DataFrame(stock_daily)
            stock_daily_df["trade_date"] = pd.to_datetime(stock_daily_df["trade_date"])
            #
            today_data = stock_daily_df.iloc[-1]
            yesterday_data = stock_daily_df.iloc[-2]
            #
            stock_daily_df["trade_volume"] = stock_daily_df["trade_volume"].astype(int)
            stock_daily_df["trade_value"] = (
                stock_daily_df["trade_value"]
                .str.replace("$", "")
                .str.replace(",", "")
                .astype(float)
            )
            stock_daily_df["opening_price"] = (
                stock_daily_df["opening_price"].str.replace("$", "").astype(float)
            )
            stock_daily_df["highest_price"] = (
                stock_daily_df["highest_price"].str.replace("$", "").astype(float)
            )
            stock_daily_df["lowest_price"] = (
                stock_daily_df["lowest_price"].str.replace("$", "").astype(float)
            )
            stock_daily_df["closing_price"] = (
                stock_daily_df["closing_price"].str.replace("$", "").astype(float)
            )
            stock_daily_df["change"] = (
                stock_daily_df["change"]
                .str.replace("$", "")
                .astype(float, errors="ignore")
            )
            stock_daily_df["transaction"] = stock_daily_df["transaction"].astype(int)

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
                "交易量",
                f'{int(today_data["trade_volume"]):,}',
                f'{int(today_data["trade_volume"])-int(yesterday_data["trade_volume"]):,}',
                delta_color="inverse",
            )

            date_long = min(stock_daily_df.shape[0], 7)
            df_long_data = pd.DataFrame(
                {
                    "trade_date": stock_daily_df.loc[
                        stock_daily_df.index[-1 : date_long * (-1) - 1 : -1],
                        "trade_date",
                    ].apply(lambda d: str(d.date())),
                    "code": [options[seleted_stock]] * date_long,
                    "name": [seleted_stock.split(" ")[-1]] * date_long,
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
                df_long_data,
                column_config={
                    "trade_date": st.column_config.TextColumn("交易日期"),
                    "code": st.column_config.TextColumn("代號"),
                    "name": st.column_config.TextColumn("名稱"),
                    "opening_price": st.column_config.NumberColumn("開盤價"),
                    "highest_price": st.column_config.NumberColumn("最高價"),
                    "lowest_price": st.column_config.NumberColumn("最低價"),
                    "closing_price": st.column_config.NumberColumn("收盤價"),
                    "trade_volume": st.column_config.NumberColumn("交易量"),
                },
                hide_index=True,
                use_container_width=True,
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
                    alt.X("trade_date").title("交易日期"),
                    alt.Y("closing_price").title("收盤價"),
                )
                .interactive(bind_y=False)
            )
            st.altair_chart(cp_chart, theme="streamlit", use_container_width=True)

            tv_chart = (
                alt.Chart(stock_daily_df)
                .mark_line(clip=True)
                .encode(
                    alt.X("trade_date").title("交易日期"),
                    alt.Y("trade_volume").title("交易量"),
                )
                .interactive(bind_y=False)
            )
            st.altair_chart(tv_chart, theme="streamlit", use_container_width=True)


if __name__ == "__main__":
    main()
