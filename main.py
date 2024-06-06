
from flask import Flask, Response, jsonify, make_response, redirect,render_template, request, session
import json
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy import create_engine,inspect,text
from urllib.parse import quote_plus
import json
import pandas as pd
# from langchain.chat_models import ChatOpenAI
from langchain_community.chat_models import ChatOpenAI
import os
import plotly.io as pio
import plotly.graph_objects as go


master_session={}
app = Flask(__name__)
app.secret_key = '123456'

app.secret_key = '123456'

# Configure Redis for session storage
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'session:'

os.environ["OPENAI_API_KEY"] = ""
llm_model = "gpt-3.5-turbo"
llm = ChatOpenAI(temperature=0.1, model=llm_model)

with open("table_structure.txt", 'r') as file:
    table_struct = file.read()

with open("example.txt", 'r') as file:
    example_st = file.read()

with open('sample_qr.txt','r') as f:
    sample = f.read()

with open("prompt.txt", 'r') as file:
    instructions = file.read()

with open("table_descriptions.txt", 'r') as file:
    desc = file.read()

with open("example_queries.txt", 'r') as file:
    Q_example = file.read()


@app.route('/')
@app.route('/login')
def login():
    print('login called ----------------')
    print('login',session)
    return render_template('login/login.html')


@app.route('/verifylogin', methods=['POST'])
def verifylogin():
    print('verifylogin called ----------------')
    if request.method == 'POST':
        username=request.form['username']
        password=request.form['password']
    with open('users.json', 'r') as f:
        users_data = json.load(f)
        if username in users_data and users_data[username] == password:
            data={'msg':'success','user':'true','password':'false'}  
            session['user']=username
            session[username]={'metadata':{}}
            print('verify login',session)
            return data
        else:
            if username in users_data:
                data={'msg':'error','user':'right','password':'wrong'}   
                return data
            else :
                data={'msg':'error','user':'wrong','password':'wrong'}
                return data

@app.route('/logout')
def logout():
    print('logout called ----------------')
    del session[session['user']]
    del session['user']
    print(session)
    return redirect('/')

@app.route('/disconnect',methods=['GET'])
def disconnect():
    print('disconnect called ----------------')
    try:
        session[session['user']]={"metadata":{}}
        print(session)
        return 'success'
    except Exception as e :
        print(e)
        return 'error'


@app.route('/main')
def main1():
    print('main1 called ----------------')
    print('vvvv',session)
    return render_template('index.html')


@app.route('/getquery',methods=['POST'])
def getquery():
    print('getquery called ----------------')
    try:
        if request.method=='POST':
            query=request.form['qry']
            print(query)
            html_table,graph_html,sqlquery= main(query)
            return jsonify({"table":html_table,"msg":"success","graph":graph_html,"query":sqlquery})
    except Exception as e:
        print(e)
        return 'error'



@app.route('/connectdb' ,methods=['POST'])
def conectdb():
    print('conectdb called ----------------')
    try:
        if (request.method == 'POST'):
            db_host=request.form['hostname']
            db_user=request.form['user']
            db_password=request.form['password']
            db_port=request.form['portno']
            db_name=request.form['database']   
            conn, connection_string, engine,mastertbl=connectmysqldb(db_user,db_password,db_host,db_port,db_name)
            print("12345",session)
            print(db_user,db_password,db_host,db_port,db_name)
            # master_session[session['user']]['conn']=conn
            session[session['user']]={'metadata':{ 
                                                    "db_host":request.form['hostname'], 
                                                    "db_user":request.form['user'],
                                                    "db_password":request.form['password'],
                                                    "db_port":request.form['portno'],
                                                    "db_name":request.form['database'],
                                                     "schema":"{}"
                                                    }}
            print(session)
            return  jsonify({"msg":"success","schema":mastertbl})
    except Exception as e:
        print(e)
        return 'error'

@app.route('/getmetadata' ,methods=['GET'])
def getmetadata():
    print('getmetadata called ----------------')
    print(session)
    try:
        if (request.method == 'GET'):
            value = session[session['user']].get('metadata') 
            print('getmetadata',value)
            print('getdata',session)
            if value :
                db_user=session[session['user']]['metadata']['db_user']
                db_password=session[session['user']]['metadata']['db_password']
                db_host=session[session['user']]['metadata']['db_host']
                db_port=session[session['user']]['metadata']['db_port']
                db_name=session[session['user']]['metadata']['db_name']
                conn, connection_string, engine,schema=connectmysqldb(db_user,db_password,db_host,db_port,db_name)
                # master_session[session['user']]['conn']=conn
                return jsonify({"metadata":session[session['user']]['metadata'],"schema":schema})
            else :
                return 'nothing'
    except Exception as e:
        print(e)
        return 'nothing'



def get_databases(engine):
    print('get_databases called ----------------')
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sys.databases"))
        return [row[0] for row in result]
    
def connectmysqldb(db_user, db_password, db_host, db_port, db_name):
    print('connectmysqldb called ----------------')
    database_structure = {}
    encoded_password = quote_plus(db_password)
    connection_string = f'mssql+pymssql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}'
    print(connection_string)
    engine = create_engine(connection_string)
    conn = engine.connect()
    print("This is conn", conn)
    database_structure[db_name] = {}
    # print(f"Database: {db_name}")
    inspector_db = inspect(engine)
    # Get list of schemas
    schemas = get_schemas(inspector_db)
    for schema in schemas:
            database_structure[db_name][schema] = {'tables': {}, 'views': {}}
            # print(f"  Schema: {schema}")

            # Get tables and views for each schema
            tables, views = get_tables_and_views(inspector_db, schema)
            # print(f"    Tables in {schema}:")
            for table in tables:
                # print(f"      {table}")
                # Get columns for each table
                columns = get_columns(inspector_db,schema,table)
                if columns:
                    database_structure[db_name][schema]['tables'][table] = {column['name']: str(column['type']) for column in columns}

            # print(f"    Views in {schema}:")
            for view in views:
                # print(f"      {view}")
                # Get columns for each view
                columns = get_columns(inspector_db, schema, view)
                if columns:
                    database_structure[db_name][schema]['views'][view] = {column['name']: str(column['type']) for column in columns}
    # engine.dispose()
    return conn, connection_string, engine ,database_structure

def get_schemas(inspector):
    # print('get_schemas called ----------------')
    return inspector.get_schema_names()
    

 
def get_tables_and_views(inspector, schema):
    # print('get_tables_and_views called ----------------')
    tables = inspector.get_table_names(schema=schema)
    views = inspector.get_view_names(schema=schema)
    return tables, views
 
 
def get_columns(inspector, schema, table_name):
    # print('get_columns called ----------------')
    try:
        return inspector.get_columns(table_name, schema=schema)
    except NoSuchTableError:
        return []
    



def get_table_names(data):
    print('get_table_names called ----------------')
    table_names = []
    for db_name, db_content in data.items():
        for schema_name, schema_content in db_content.items():
            for table_or_view, tables_and_views in schema_content.items():
                if table_or_view == 'tables':
                    for table_name in tables_and_views:
                        table_names.append(table_name)
    return table_names

def primary(conn, table_name):
    print('primary called ----------------')
    primary_key_query = text("""
    SELECT COLUMN_NAME
    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
    WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_SCHEMA + '.' + CONSTRAINT_NAME), 'IsPrimaryKey') = 1
    AND TABLE_NAME = :table_name;
    """)
    primary1 = pd.read_sql(primary_key_query, conn, params={"table_name": table_name})
    return primary1['COLUMN_NAME'].tolist()

def foreign(conn, table_name):
    print('foreign called ----------------')
    foreign_key_query = text("""
    SELECT COLUMN_NAME
    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
    WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_SCHEMA + '.' + CONSTRAINT_NAME), 'IsForeignKey') = 1
    AND TABLE_NAME = :table_name;
    """)
    foreign1 = pd.read_sql(foreign_key_query, conn, params={"table_name": table_name})
    return foreign1['COLUMN_NAME'].tolist()

def generate_table_descriptions(conn, structure, table_names):
    print('generate_table_descriptions called ----------------')
    descriptions = {}

    for database, schemas in structure.items():
        for schema, content in schemas.items():
            for table_name, columns in content["tables"].items():
                # Check if the table exists in the database
                if table_name not in table_names:
                    print(f"Table {table_name} does not exist in the database. Skipping.")
                    continue

                # Get primary keys for the table
                primary_keys = primary(conn, table_name)

                # Get Foreign keys for the table
                foreign_keys = foreign(conn, table_name)

                # Generate table description
                table_description = {}
                for column, dtype in columns.items():
                    description = f"{column.replace('_', ' ').capitalize()} of type {dtype}"
                    if column in primary_keys:
                        description += " (Primary Key)"
                    table_description[column] = description
                    if column in foreign_keys:
                        description += " (Foreign Key)"
                    table_description[column] = description
                descriptions[table_name] = table_description

    return descriptions


def test_query(conn, query):
    print('test_query called ----------------')
    try:
        result = conn.execute(text(query))
        result.fetchall()
        return True
    except Exception as e:
        print(f"Query failed: {query}\nError: {e}")
        return False
    
def extract_tables(structure):
    print('extract_tables called ----------------')
    # Function to extract table columns dynamically
    for database, schemas in structure.items():
        for schema, content in schemas.items():
            return content["tables"]




@app.route('/generatedescription' ,methods=['POST'])
def gendescription():
    # try:
        print('gendescription called ----------------')
        if (request.method == 'POST'):
            structure=request.form['schema']
            print(type(structure))
            print(structure)
            print(session)
            conn=get_connection()
            json_dict =json.loads(structure)
            print(type(json_dict))
            print(json_dict)
            table_names =get_table_names(json_dict)
            descriptions =generate_table_descriptions(conn, json_dict, table_names)
            # print("Structure of tables:")
            # print(json.dumps(descriptions, indent=2))
            with open("table_structure.txt", "w") as file:
                file.write(json.dumps(descriptions, indent=2))
            print(40*"-")
            print("structure")
            print(structure)
            print("+++",session[session['user']]['metadata'])
            session[session['user']]['metadata']['schema']=structure #schema
            session.modified = True
            print('adb',session)    
            return jsonify({"msg":'success',"metadata":session[session['user']]['metadata']})
    # except Exception as e :
    #     print(e)
    #     return jsonify({"msg":'error',"metadata":session[session['user']]['metadata']})


def get_connection():
    print('get_connection called ----------------')
    db_user=session[session['user']]['metadata']['db_user']
    db_password=session[session['user']]['metadata']['db_password']
    db_host=session[session['user']]['metadata']['db_host']
    db_port=session[session['user']]['metadata']['db_port']
    db_name=session[session['user']]['metadata']['db_name']
    encoded_password = quote_plus(db_password)
    connection_string = f'mssql+pymssql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}'
    print(connection_string)
    engine = create_engine(connection_string)
    conn = engine.connect()
    return conn

def main(nlquestion):
    print('main called ----------------')
    conn=get_connection()
    descript = f"""You have been provided with table structure. Generate the table description for the provided table structure.\
Example:
{example_st}

Input:
{table_struct}

Output:

"""
    # print(20*'+')
    # print(descript)
    description_table = llm.invoke(descript)
    try:
        description_dict = json.loads(description_table.content)
        with open("table_descriptions.txt", "w") as file:
            file.write(json.dumps(description_dict, indent=2))
        # print("JSON successfully written to table_descriptions.txt")
    except json.JSONDecodeError as e:
        print("JSONDecodeError:", e)
        # Handle the case where the content is not valid JSON
        with open("table_descriptions.txt", "w") as file:
            file.write(description_table.content)
        # print("Raw output written to table_descriptions.txt for further analysis")

    sample_query_prompt = f"""Consider you are a expert in mssql and you can give correct SQL to fetch data everytime.\
Database Schema Description is given below as "INPUT" and Provide the "OUTPUT"\
{sample}\

INPUT: 
{desc}

OUTPUT:

"""
    
    Sql_demo_query = llm.invoke(sample_query_prompt)
    sample_queries = Sql_demo_query.content
    with open("example_queries.txt","w") as f:
        f.write(sample_queries)

    # nlquestion = input("Enter your question?: ")

    prompt_sql = f"""Consider you are a expert in mssql and you can give correct SQL to fetch data everytime. 
    Now, using the Table description and Instructions given below, convert the user's natural language query to mssql Query -

    TABLE DESCRIPTION:
    {desc}

    INSTRUCTIONS:
    {instructions}

    EXAMPLE:
    {Q_example}

    INPUT:
    {nlquestion}
    ANSWER:


"""
    Sql_ans = llm.invoke(prompt_sql)
    ans = Sql_ans.content.replace("\n"," ").replace("Answer","").replace(":"," ").replace('"','')
    # print(ans)
    df = pd.read_sql(text(ans), conn)
    # print(df)
    with open("graph_prompt.txt", 'r') as file:
        g_prompt = file.read()

    graph_prompt = f"""{g_prompt}\

    INPUT:
    {df}

    OUTPUT:

    """

    Sql_graph = llm.invoke(graph_prompt)
    img_code = Sql_graph.content.replace("python","").replace("`","")
    graph = {}
    # print(img_code)
    exec(img_code, graph)
    g1 = graph
    # print(g1)
    conn.close()
    newdf= df.to_html(index=False)
    new_graph = pio.to_html(g1['graph_object'], full_html=False,include_plotlyjs=False,config={'responsive': True},default_height="338px",default_width="100%",div_id="mygraph")
    return(newdf,new_graph,ans)

if __name__ == '__main__':
    app.run(debug=True)
