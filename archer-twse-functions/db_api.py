# Register this blueprint by adding the following line of code
# to your entry point file.
# app.register_functions(db_api)
#
# Please refer to https://aka.ms/azure-functions-python-blueprints


import azure.functions as func
import logging

import psycopg
import json
import os

db_api = func.Blueprint()


@db_api.route(route="get_stock_list", auth_level=func.AuthLevel.ANONYMOUS)
def get_stock_list(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    try:
        connection_string = os.environ["AZURE_POSTGRESQL_CONNECTIONSTRING"]
        with psycopg.connect(connection_string) as cnx:
            cur = cnx.cursor()
            query = "SELECT code, name FROM stock ORDER BY code;"
            cur.execute(query)
            stock_list = [{"code": code, "name": name} for code, name in cur.fetchall()]

        return func.HttpResponse(
            json.dumps(stock_list, ensure_ascii=False),
            status_code=200,
        )
    except Exception as e:
        return func.HttpResponse(
            str(e),
            status_code=500,
        )


@db_api.route(route="http_trigger", auth_level=func.AuthLevel.ANONYMOUS)
def http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    stock = req.params.get("stock")
    if not stock:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            stock = req_body.get("stock")

    if stock:
        try:
            connection_string = os.environ["AZURE_POSTGRESQL_CONNECTIONSTRING"]
            with psycopg.connect(connection_string) as cnx:
                cur = cnx.cursor()

                query = """
                        SELECT trade_date, trade_volume, trade_value, opening_price, 
                        highest_price, lowest_price, closing_price, change, transaction
                            FROM daily_price 
                            WHERE stock_code = %s
                            ORDER BY trade_date;
                    """

                cur.execute(query, (stock,))

                stock_daily = [
                    {
                        "trade_date": str(trade_date),
                        "trade_volume": str(trade_volume),
                        "trade_value": str(trade_value),
                        "opening_price": str(opening_price),
                        "highest_price": str(highest_price),
                        "lowest_price": str(lowest_price),
                        "closing_price": str(closing_price),
                        "change": str(change),
                        "transaction": str(transaction),
                    }
                    for trade_date, trade_volume, trade_value, opening_price, highest_price, lowest_price, closing_price, change, transaction in cur.fetchall()
                ]

            return func.HttpResponse(
                json.dumps(stock_daily, ensure_ascii=False),
            )
        except Exception as e:
            return func.HttpResponse(
                str(e),
                status_code=500,
            )
    else:
        return func.HttpResponse(
            "This HTTP triggered function executed successfully. Pass a stock in the query string or in the request body for a personalized response.",
            status_code=200,
        )
