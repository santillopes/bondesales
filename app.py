import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_session import Session
from datetime import datetime

# Configuração do Aplicativo Flask
app = Flask(__name__)

# Configuração de Sessão
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Inicialização do Banco de Dados
db = SQL("sqlite:///sales.db")

# --- Funções Auxiliares de Consulta ---

def get_all_lookups():
    """Recupera todos os dados de lookup (produtos, marcas, etc.)."""
    return {
        "users": db.execute("SELECT id, name FROM users ORDER BY name"),
        "products": db.execute("SELECT id, name FROM products ORDER BY name"),
        "brands": db.execute("SELECT id, name FROM brands ORDER BY name"),
        "sizes": db.execute("SELECT id, name FROM sizes ORDER BY name"),
        "colors": db.execute("SELECT id, name FROM colors ORDER BY name"),
    }

def calculate_days_diff(start_date_str, end_date_str=None):
    """
    Calcula a diferença em dias.
    Se end_date_str for None, calcula até a data de hoje (datetime.now).
    """
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = datetime.now() # Usa data atual se não houver data final
            
        return (end_date - start_date).days
    except Exception:
        return None

def format_date_pt(date_str):
    """Formata a data de YYYY-MM-DD para DD/MM/YYYY. Retorna None se a entrada for None."""
    if not date_str:
        return None
    try:
        dt_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return dt_obj.strftime('%d/%m/%Y')
    except Exception:
        return date_str


def get_user_data(user_id):
    """
    Recupera pedidos, posts e dados de vendas consolidados para um usuário específico.
    """
    
    # 1. Recuperar Pedidos (Orders)
    orders = db.execute("""
        SELECT 
            orders.id AS order_id, 
            products.name AS product_name,
            brands.name AS brand_name,
            colors.name AS color_name,
            sizes.name AS size_name,
            orders.order_date,
            orders.delivery_date,
            orders.price,
            orders.deliver_tax,
            (orders.price + orders.deliver_tax) AS total_cost,
            sales.id AS sale_id,
            sales.status AS status,
            sales.post_id
        FROM orders
        JOIN products ON products.id = orders.product_id
        JOIN brands ON brands.id = orders.brand_id
        JOIN colors ON colors.id = orders.color_id
        JOIN sizes ON sizes.id = orders.size_id
        JOIN sales ON sales.order_id = orders.id
        WHERE sales.user_id = ?
        ORDER BY orders.order_date DESC
    """, user_id)

    # 2. Recuperar Posts - ADICIONADO LIKES, VIEWS E OFFERS (PROPOSALS)
    posts = db.execute("""
        SELECT 
            posts.id AS post_id, 
            posts.post_date,
            posts.first_price,
            posts.sell_price,
            posts.ad_tax,
            posts.sell_date,
            posts.likes,      -- Adicionado
            posts.views,      -- Adicionado
            posts.offers AS proposals, -- Adicionado e renomeado para compatibilidade com HTML
            orders.id AS order_id,
            orders.order_date AS order_date,
            orders.delivery_date AS delivery_date,
            orders.price AS order_price,
            orders.deliver_tax AS order_deliver_tax,
            products.name AS product_name,
            brands.name AS brand_name,
            colors.name AS color_name,
            sizes.name AS size_name,
            sales.status AS status
        FROM posts
        JOIN orders ON orders.id = posts.order_id
        JOIN products ON products.id = orders.product_id
        JOIN brands ON brands.id = orders.brand_id
        JOIN colors ON colors.id = orders.color_id
        JOIN sizes ON sizes.id = orders.size_id
        JOIN sales ON sales.post_id = posts.id
        WHERE sales.user_id = ?
        ORDER BY posts.post_date DESC
    """, user_id)

    # --- PROCESSAMENTO E CÁLCULOS DE TEMPO (ANTES DA FORMATAÇÃO DAS DATAS) ---

    # Processar Orders para adicionar contagens de dias
    for o in orders:
        if o['delivery_date']:
            # Se já chegou, calcula dias que demorou (Order -> Delivery)
            o['days_to_delivery'] = calculate_days_diff(o['order_date'], o['delivery_date'])
            o['days_since_order'] = None 
        else:
            # Se não chegou, calcula dias desde o pedido até hoje (Order -> Hoje)
            o['days_to_delivery'] = None
            o['days_since_order'] = calculate_days_diff(o['order_date'], None)

    # Processar Posts para adicionar contagens de dias
    for p in posts:
        if p['status'] == 'sold' and p['sell_date']:
             # Se vendido, calcula dias que demorou a vender (Post -> Sell)
            p['days_to_sale'] = calculate_days_diff(p['post_date'], p['sell_date'])
            p['days_since_post'] = None
        else:
             # Se ativo, calcula dias desde o post até hoje (Post -> Hoje)
            p['days_to_sale'] = None
            p['days_since_post'] = calculate_days_diff(p['post_date'], None)


    # 3. Preparar a Tabela de Vendas (Sales Table) - Apenas itens com status 'sold'
    sales_data = []
    for p in posts:
        if p['status'] == 'sold' and p['sell_price'] is not None and p['sell_date'] is not None:
            
            # Cálculo de Gastos Totais (Encomenda + Destaques)
            total_gastos = (p['order_price'] or 0) + (p['order_deliver_tax'] or 0) + (p['ad_tax'] or 0)
            
            # Cálculo de Lucro
            lucro = (p['sell_price'] or 0) - total_gastos
            
            # Cálculo de Tempo Total (Encomenda -> Venda)
            # O html pede 'days_to_sale_total'
            tempo_total = calculate_days_diff(p['order_date'], p['sell_date'])

            sales_data.append({
                'product_info': f"{p['product_name']} / {p['brand_name']}", # Simplificado para caber na tabela, mas tem acesso aos nomes individuais
                'brand_name': p['brand_name'],
                'size_name': p['size_name'],
                'color_name': p['color_name'],
                'total_gastos': total_gastos,
                'ad_tax': p['ad_tax'] or 0,
                'sell_price': p['sell_price'],
                'lucro': lucro,
                'sell_date': format_date_pt(p['sell_date']),
                'days_to_sale_total': tempo_total, # Nome da variável atualizado para o HTML
                'tempo_total': tempo_total, # Mantendo backup
                'post_id': p['post_id'],
                'post_id': p['post_id']
            })

    # --- FORMATAÇÃO FINAL DE DATAS PARA DISPLAY ---
    # Formatar as datas para dd/mm/yyyy
    for o in orders:
        o['order_date'] = format_date_pt(o['order_date'])
        o['delivery_date'] = format_date_pt(o['delivery_date'])
        o['total_cost'] = (o['price'] or 0) + (o['deliver_tax'] or 0)

    for p in posts:
        p['post_date'] = format_date_pt(p['post_date'])
        p['sell_date'] = format_date_pt(p['sell_date'])


    return orders, posts, sales_data

def calculate_user_metrics_from_data(orders, posts, sales_data):
    """Calcula métricas financeiras e de contagem a partir das listas de dados."""
    
    # 1. CÁLCULOS FINANCEIROS DE VENDAS CONCRETAS
    faturacao = sum(item['sell_price'] for item in sales_data)
    gastos_totais = sum(item['total_gastos'] for item in sales_data)
    lucro_total = faturacao - gastos_totais

    # Multiplicador (ROI)
    multiplicador = 0.0
    if gastos_totais > 0:
        multiplicador = lucro_total / gastos_totais
    
    # 2. CONTAGEM DE ENCOMENDAS
    count_stock = sum(1 for o in orders if o['status'] == 'stock')
    count_chegar = sum(1 for o in orders if o['status'] == 'shipping')
    count_vendidas = len(sales_data)

    # 3. CÁLCULO DE TEMPO DE STOCK (Projeção)
    dias_fim_stock = 0
    stock_atual = count_stock + count_chegar

    if stock_atual > 0:
        total_dias_venda = 0
        valid_sales = 0
        
        # Usamos o cálculo de dias já feito no processamento anterior
        for p in posts:
            if p['status'] == 'sold' and p.get('days_to_sale'):
                total_dias_venda += p['days_to_sale']
                valid_sales += 1
        
        tempo_venda_medio = (total_dias_venda / valid_sales) if valid_sales > 0 else 60 

        if tempo_venda_medio > 0:
            dias_fim_stock = stock_atual * tempo_venda_medio
        else:
            dias_fim_stock = 365 


    # 4. NOVAS MÉTRICAS DE STOCK E PROJEÇÃO DE LUCRO
    invested_stock_cost = 0
    estimated_stock_profit = 0

    for o in orders:
        if o['status'] in ['shipping', 'stock']:
            
            cost_initial = (o['price'] or 0) + (o['deliver_tax'] or 0)
            invested_stock_cost += cost_initial
            
            if o['status'] == 'shipping':
                estimated_profit_item = cost_initial * multiplicador
                estimated_stock_profit += estimated_profit_item
            
            elif o['status'] == 'stock':
                # Procura o post correspondente
                post = next((p for p in posts if p['order_id'] == o['order_id']), None)
                
                if post and post['first_price'] is not None:
                    announced_price = post['first_price']
                    ad_tax_cost = (post['ad_tax'] or 0)
                    total_cost_with_ad = cost_initial + ad_tax_cost
                    estimated_profit_item = announced_price - total_cost_with_ad
                    estimated_stock_profit += estimated_profit_item
                else:
                    estimated_profit_item = cost_initial * multiplicador
                    estimated_stock_profit += estimated_profit_item

    return {
        'faturacao': faturacao,
        'gastos': gastos_totais,
        'lucro': lucro_total,
        'multiplicador': multiplicador,
        'encomendas_stock': count_stock,
        'encomendas_chegar': count_chegar,
        'encomendas_vendidas': count_vendidas,
        'dias_fim_stock': dias_fim_stock,
        'invested_stock_cost': invested_stock_cost,
        'estimated_stock_profit': estimated_stock_profit,
    }

def get_post_data(post_id):
    """Busca dados de um post específico."""
    # Exemplo: return db.execute("SELECT * FROM posts WHERE id = ?", post_id)[0]
    return db.execute("SELECT * FROM posts WHERE id = ?", (post_id,))

def get_order_data(order_id):
    """Busca dados de uma encomenda específica."""
    # Exemplo: return db.execute("SELECT * FROM orders WHERE id = ?", order_id)[0]
    return db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))

def get_post_by_product_id(product_id):
    """Busca um post associado a um product_id."""
    # Retorna o ID do post, se encontrado.
    # Exemplo: return db.execute("SELECT id FROM posts WHERE product_id = ?", product_id)
    return db.execute("SELECT id FROM posts WHERE product_id = ?", (product_id,))


# --- Rotas Principais ---

@app.route("/", methods=["GET"])
def index():
    """Página inicial: Seleção de usuário, formulários de adição e visualização de dados."""
    lookups = get_all_lookups()
    
    selected_user_id_str = request.args.get("user_id")
    selected_user_id = None
    selected_user_name = None 
    
    orders = [] 
    posts = []
    sales_data = []
    user_metrics = None 
    
    if selected_user_id_str and selected_user_id_str.isdigit():
        try:
            selected_user_id = int(selected_user_id_str)
            
            user_result = db.execute("SELECT name FROM users WHERE id = ?", selected_user_id)
            if user_result:
                selected_user_name = user_result[0]['name']

            orders, posts, sales_data = get_user_data(selected_user_id)
            user_metrics = calculate_user_metrics_from_data(orders, posts, sales_data)
            
        except Exception as e:
            flash(f"Erro ao carregar dados. Verifique a estrutura do DB. Detalhes: {e}", "danger")
            selected_user_id = None

    return render_template("index.html",
                            selected_user_id=selected_user_id,
                            selected_user_name=selected_user_name,
                            orders=orders,
                            posts=posts,
                            sales_data=sales_data,
                            user_metrics=user_metrics,
                            **lookups)


@app.route("/add_order", methods=["POST"])
def add_order():
    """Adiciona um novo pedido e uma nova venda (status 'shipping')."""
    user_id = request.form.get("user_id")
    product_id = request.form.get("product_id")
    brand_id = request.form.get("brand_id")
    size_id = request.form.get("size_id")
    color_id = request.form.get("color_id")
    price = request.form.get("price")
    deliver_tax = request.form.get("deliver_tax") or 0 
    order_date = request.form.get("order_date")
    delivery_date = request.form.get("delivery_date") or None

    if not all([user_id, product_id, brand_id, size_id, color_id, price, order_date]):
        flash("Todos os campos obrigatórios do pedido devem ser preenchidos.", "warning")
        return redirect(url_for('index', user_id=user_id))

    try:
        order_id = db.execute("""
            INSERT INTO orders (product_id, brand_id, size_id, color_id, price, deliver_tax, order_date, delivery_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, product_id, brand_id, size_id, color_id, price, deliver_tax, order_date, delivery_date)
        
        initial_status = "shipping"
        if delivery_date:
            initial_status = "stock"

        db.execute("""
            INSERT INTO sales (order_id, user_id, status)
            VALUES (?, ?, ?)
        """, order_id, user_id, initial_status)
        
        flash("Encomenda adicionada com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao adicionar encomenda: {e}", "danger")

    return redirect(url_for('index', user_id=user_id))


@app.route("/add_post", methods=["POST"])
def add_post():
    """Adiciona um novo post e atualiza a venda (status 'stock')."""
    user_id = request.form.get("user_id")
    order_id = request.form.get("order_id")
    first_price = request.form.get("first_price") 
    sell_price = request.form.get("sell_price") or None 
    ad_tax = request.form.get("ad_tax") or 0
    post_date = request.form.get("post_date")
    sell_date = request.form.get("sell_date") or None
    
    # Novos campos opcionais
    views = request.form.get("views") or 0
    likes = request.form.get("likes") or 0
    proposals = request.form.get("proposals") or 0 # DB usa 'offers'

    if not all([user_id, order_id, first_price, post_date]):
        flash("Todos os campos obrigatórios do post devem ser preenchidos.", "warning")
        return redirect(url_for('index', user_id=user_id))
        
    sale_status = db.execute("SELECT status FROM sales WHERE order_id = ?", order_id)
    if not sale_status or sale_status[0]['status'] == 'shipping':
        flash("Não é possível criar um post. A encomenda ainda está 'shipping'.", "danger")
        return redirect(url_for('index', user_id=user_id))
        
    try:
        if sell_date and not sell_price:
             flash("Se a Data da Venda for preenchida, o Preço Vendido também é obrigatório.", "warning")
             return redirect(url_for('index', user_id=user_id))
        
        # Inserir com os novos campos (offers = proposals)
        # Atenção: DB usa 'offers', HTML usa 'proposals'
        post_id = db.execute("""
            INSERT INTO posts (order_id, first_price, sell_price, ad_tax, post_date, sell_date, views, likes, offers)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, order_id, first_price, sell_price, ad_tax, post_date, sell_date, views, likes, proposals)
        
        new_status = 'sold' if sell_date else 'stock'

        db.execute("""
            UPDATE sales
            SET post_id = ?, status = ?
            WHERE order_id = ?
        """, post_id, new_status, order_id)
        
        flash("Post adicionado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao adicionar post: {e}", "danger")

    return redirect(url_for('index', user_id=user_id))


# --- Rotas de Edição ---

@app.route("/edit_order/<int:order_id>", methods=["GET"])
def edit_order(order_id):
    order = db.execute("""
        SELECT orders.*, sales.user_id, sales.status
        FROM orders
        JOIN sales ON sales.order_id = orders.id
        WHERE orders.id = ?
    """, order_id)
    
    if not order:
        flash("Pedido não encontrado.", "danger")
        return redirect(url_for('index'))
    
    lookups = get_all_lookups()
    return render_template("edit_order.html", order=order[0], **lookups)


@app.route("/update_order", methods=["POST"])
def update_order():
    """Atualiza uma encomenda no banco de dados."""
    order_id = request.form.get("order_id")
    user_id = request.form.get("user_id")

    # 1. Obter dados do formulário
    product_id = request.form.get("product_id")
    brand_id = request.form.get("brand_id")
    size_id = request.form.get("size_id")
    color_id = request.form.get("color_id")
    price = request.form.get("price")
    deliver_tax = request.form.get("deliver_tax") or 0
    order_date = request.form.get("order_date")
    delivery_date = request.form.get("delivery_date") or None # Pode ser None

    # 2. Lógica de Status (stock se delivery_date preenchido)
    status = "shipping"
    if delivery_date:
        status = "stock"
    
    # 3. Execução da Atualização
    try:
        db.execute("""
            UPDATE orders SET
                product_id = ?, brand_id = ?, size_id = ?, color_id = ?,
                price = ?, deliver_tax = ?, order_date = ?, delivery_date = ?, status = ?
            WHERE id = ? AND user_id = ?
        """, (product_id, brand_id, size_id, color_id, price, deliver_tax, 
              order_date, delivery_date, status, order_id, user_id))

        # 4. Atualizar o status do produto associado (importante se o status da encomenda mudou)
        db.execute("UPDATE products SET status = ? WHERE id = ? AND user_id = ?", (status, product_id, user_id))

        flash("Encomenda atualizada com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao atualizar a encomenda: {e}", "danger")

    return redirect(url_for('index', user_id=user_id))

@app.route("/delete_order", methods=["POST"])
def delete_order():
    """
    Deleta uma encomenda.
    Deleta também o post e os registos de venda associados, mas MANTÉM o registo do produto.
    """
    order_id = request.form.get("order_id")
    user_id = request.form.get("user_id")

    # 1. Buscar explicitamente o product_id E validar a posse (user_id) em um único passo.
    order_data = db.execute(
        "SELECT product_id FROM orders WHERE id = ? AND user_id = ?", 
        (order_id, user_id)
    )

    if not order_data:
        # Se a query não retornar resultados, a encomenda não existe ou não pertence ao utilizador.
        flash("Encomenda não encontrada ou acesso negado.", "danger")
        return redirect(url_for('index', user_id=user_id))

    # O registo é válido, extrair o product_id
    product_id = order_data[0]['product_id']

    try:
        # 2. Deletar a Encomenda
        db.execute("DELETE FROM orders WHERE id = ? AND user_id = ?", (order_id, user_id))

        # 3. Deletar registros associados a esta encomenda na tabela `sales` 
        db.execute("DELETE FROM sales WHERE order_id = ? AND user_id = ?", (order_id, user_id))
        
        # 4. Buscar e Deletar Post associado ao produto (se existir)
        post = get_post_by_product_id(product_id)
        if post:
            post_id = post[0]['id']
            # Deletar o post, garantindo que também pertence ao user_id
            db.execute("DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, user_id))
            flash(f"Post ID {post_id} associado foi excluído.", "info")
            
        # 5. [PASSO REMOVIDO] O registo do Produto é MANTIDO.
        
        flash("Encomenda, registos de venda e post associado (se existir) excluídos com sucesso.", "success")

    except Exception as e:
        flash(f"Erro ao deletar a encomenda: {e}", "danger")

    return redirect(url_for('index', user_id=user_id))


@app.route("/edit_post/<int:post_id>", methods=["GET"])
def edit_post(post_id):
    post = db.execute("""
        SELECT 
            posts.*,
            posts.offers AS proposals, -- Alias para o formulário se usar o mesmo nome
            orders.id AS order_id,
            products.name AS product_name,
            sales.user_id,
            sales.status
        FROM posts
        JOIN orders ON orders.id = posts.order_id
        JOIN products ON products.id = orders.product_id
        JOIN sales ON sales.post_id = posts.id
        WHERE posts.id = ?
    """, post_id)
    
    if not post:
        flash("Post não encontrado.", "danger")
        return redirect(url_for('index'))
    
    return render_template("edit_post.html", post=post[0])




@app.route("/update_post", methods=["POST"])
def update_post():
    """Atualiza um post no banco de dados com os novos campos (Views, Likes, Propostas)."""
    post_id = request.form.get("post_id")
    user_id = request.form.get("user_id")

    # 1. Obter dados obrigatórios e opcionais
    first_price = request.form.get("first_price")
    sell_price = request.form.get("sell_price") or None # Pode ser None
    ad_tax = request.form.get("ad_tax") or 0
    post_date = request.form.get("post_date")
    sell_date = request.form.get("sell_date") or None # Pode ser None

    # Novos campos de métricas
    views = request.form.get("views") or 0
    likes = request.form.get("likes") or 0
    proposals = request.form.get("proposals") or 0

    # 2. Lógica de Status (SOLD se sell_date preenchido)
    status = "POSTED"
    if sell_date:
        status = "SOLD"
        if not sell_price:
            flash("Erro: A Data da Venda foi preenchida, mas o Preço Vendido está vazio.", "danger")
            return redirect(url_for('edit_post', post_id=post_id))
    
    # 3. Execução da Atualização
    try:
        db.execute("""
            UPDATE posts SET
                first_price = ?, sell_price = ?, ad_tax = ?, post_date = ?,
                sell_date = ?, status = ?, views = ?, likes = ?, proposals = ?
            WHERE id = ? AND user_id = ?
        """, (first_price, sell_price, ad_tax, post_date, sell_date, status,
              views, likes, proposals, post_id, user_id))

        flash("Post atualizado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao atualizar o post: {e}", "danger")

    return redirect(url_for('index', user_id=user_id))

@app.route("/delete_post", methods=["POST"])
def delete_post():
    """
    Deleta um post.
    Se o post estava como 'SOLD', o status do produto associado volta para 'STOCK'.
    """
    post_id = request.form.get("post_id")
    user_id = request.form.get("user_id")
    
    # 1. Buscar dados atuais do post antes de deletar
    post = get_post_data(post_id)
    if not post or post[0]['user_id'] != int(user_id):
        flash("Post não encontrado ou acesso negado.", "danger")
        return redirect(url_for('index', user_id=user_id))
    
    post_data = post[0]
    
    # 2. Deletar o Post
    try:
        db.execute("DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, user_id))
        flash("Post excluído com sucesso!", "success")
        
        # 3. Verificar regra de negócio: Se estava vendido, atualizar produto
        if post_data['status'] == 'SOLD':
            product_id = post_data['product_id']
            db.execute("UPDATE products SET status = 'STOCK' WHERE id = ? AND user_id = ?", (product_id, user_id))
            flash(f"Produto ID {product_id} associado foi movido para STOCK.", "info")

    except Exception as e:
        flash(f"Erro ao deletar o post: {e}", "danger")

    return redirect(url_for('index', user_id=user_id))

app.jinja_env.globals.update(format_date_pt=format_date_pt)