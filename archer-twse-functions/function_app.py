import logging
import azure.functions as func
from db_api import db_api

from datetime import date, datetime
import pandas as pd
import requests
import psycopg
import json
import os

app = func.FunctionApp()

app.register_functions(db_api)


fields_dict = {
    "證券代號": "stock_code",
    "證券名稱": "stock_name",
    "成交股數": "trade_volume",
    "成交金額": "trade_value",
    "開盤價": "opening_price",
    "最高價": "highest_price",
    "最低價": "lowest_price",
    "收盤價": "closing_price",
    "漲跌價差": "change",
    "成交筆數": "transaction",
}


def get_daily_price(today: date):
    """get stock daily data from twse api"""
    response = requests.get(os.environ["twse_daily_price_url"])

    try:
        response.raise_for_status()
        response_dict = json.loads(response.text)

        assert (
            response_dict.get("stat") == "OK"
        ), f'response stat is {response_dict.get("stat")}'
        assert response_dict.get("date") == today.strftime(
            "%Y%m%d"
        ), f"response date error. {response_dict.get('date')}"

        fields = response_dict.get("fields")
        data = response_dict.get("data")
        all_daily_data = [dict(zip(fields, stock_data)) for stock_data in data]

    except Exception as e:
        message = f"[TWSE] {today} {str(e)}"
        line_notify(message)
        all_daily_data = []

    return all_daily_data


def transform_to_df(all_daily_data: list):
    all_daily_data_df = pd.DataFrame(all_daily_data)
    all_daily_data_df = all_daily_data_df.rename(columns=fields_dict, errors="raise")

    all_daily_data_df["trade_volume"] = all_daily_data_df["trade_volume"].str.replace(
        ",", ""
    )
    all_daily_data_df["change"] = all_daily_data_df["change"].map(
        lambda x: None if x.startswith("X") else x
    )
    all_daily_data_df["transaction"] = all_daily_data_df["transaction"].str.replace(
        ",", ""
    )

    return all_daily_data_df


def get_stock_uuid(cur: psycopg.Cursor, stock: pd.DataFrame) -> str:
    """insert to Table stock and get stock uuid"""

    cur.execute("SELECT uuid FROM stock WHERE code=%s;", (stock["stock_code"],))
    stock_uuid = cur.fetchone()

    if stock_uuid:
        stock_uuid = stock_uuid[0]
    else:
        cur.execute(
            "INSERT INTO stock(name, code) VALUES (%s, %s) RETURNING uuid;",
            (stock["stock_name"], stock["stock_code"]),
        )
        stock_uuid = cur.fetchone()[0]

    return stock_uuid


def set_daily_price(
    cur: psycopg.Cursor, stock: pd.DataFrame, stock_uuid: str, today: date
) -> None:
    """insert to Table daily_price"""

    cur.execute(
        (
            "INSERT INTO daily_price(stock_id, trade_date, stock_code, trade_volume, trade_value, opening_price, highest_price, lowest_price, closing_price, change, transaction)"
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);"
        ),
        [
            stock_uuid,
            today,
            stock["stock_code"],
            stock["trade_volume"] or None,
            stock["trade_value"] or None,
            stock["opening_price"] or None,
            stock["highest_price"] or None,
            stock["lowest_price"] or None,
            stock["closing_price"] or None,
            stock["change"] or None,
            stock["transaction"] or None,
        ],
    )

    return


def line_notify(message: str) -> None:
    Line_Notify_Account = {
        "token": os.environ["line_token"],
    }

    headers = {
        "Authorization": "Bearer " + Line_Notify_Account["token"],
        "Content-Type": "application/x-www-form-urlencoded",
    }

    params = {"message": message}

    r = requests.post(
        "https://notify-api.line.me/api/notify", headers=headers, params=params
    )

    logging.info(f"{r.status_code} {params}")
    return


@app.timer_trigger(
    schedule="0 30 6 * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False
)
def get_daily_to_db(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info("The timer is past due!")

    #
    today = datetime.now().date()
    logging.info(f"today: {today}")

    all_daily_data = get_daily_price(today)
    # logging.info(f"all_daily_data: {all_daily_data}")

    if not all_daily_data:
        return

    try:
        connection_string = os.environ["AZURE_POSTGRESQL_CONNECTIONSTRING"]
        with psycopg.connect(connection_string) as cnx:
            cur = cnx.cursor()

            all_daily_data_df = transform_to_df(all_daily_data)

            for _, stock in all_daily_data_df.iterrows():
                stock_uuid = get_stock_uuid(cur, stock)
                logging.info(f"stock_uuid: {stock_uuid}")
                set_daily_price(cur, stock, stock_uuid, today)

            cnx.commit()

        message = f"[TWSE] {today} success"

    except Exception as e:
        message = f"[TWSE] {today} error: {str(e)}"

    logging.info(f"message: {message}")
    line_notify(message)

    logging.info("Python timer trigger function executed.")
