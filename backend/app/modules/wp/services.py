# app/modules/wp/services.py
from decimal import Decimal
from .db_wp import get_wp_conn

def get_wp_products():
    """
    Liest alle WooCommerce-Produkte (ID, Titel, Preis) aus WordPress.
    """
    conn = get_wp_conn()
    try:
        cur = conn.cursor(dictionary=True)

        # Produkte holen
        cur.execute("""
            SELECT ID, post_title
            FROM wp_posts
            WHERE post_type = 'product'
              AND post_status = 'publish'
            ORDER BY post_title ASC
        """)
        products = []
        for row in cur:
            pid = row["ID"]
            title = row["post_title"]

            cur2 = conn.cursor()
            cur2.execute("""
                SELECT meta_value
                FROM wp_postmeta
                WHERE post_id = %s AND meta_key = '_price'
                LIMIT 1
            """, (pid,))
            price_row = cur2.fetchone()
            price = Decimal(price_row[0]) if price_row and price_row[0] else Decimal("0")
            cur2.close()

            products.append({
                "id": pid,
                "name": title,
                "price": float(price),
            })
        cur.close()
        return products
    finally:
        conn.close()
