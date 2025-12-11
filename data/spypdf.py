import pypdf
import os

def listar_campos_pdf(arquivo):
    try:
        reader = pypdf.PdfReader(arquivo)
        fields = reader.get_fields()
        
        if fields:
            print(f"--- CAMPOS ENCONTRADOS EM {arquivo} ---")
            for field_name, value in fields.items():
                # Tenta pegar o tipo do campo se possível
                tipo = value.get('/FT', 'Desconhecido')
                print(f"Campo: '{field_name}' | Tipo: {tipo}")
        else:
            print("NENHUM CAMPO DE FORMULÁRIO ENCONTRADO.")
            print("Se o PDF for apenas uma imagem/design, precisaremos usar coordenadas X/Y (mais difícil).")
            
    except Exception as e:
        print(f"Erro ao ler PDF: {e}")

# Certifique-se que o arquivo 'brancasheet.pdf' está na mesma pasta ou na pasta data/
if __name__ == "__main__":
    # Tenta achar na raiz ou em data/
    if os.path.exists("brancasheet.pdf"):
        listar_campos_pdf("brancasheet.pdf")
    elif os.path.exists("data/brancasheet.pdf"):
        listar_campos_pdf("data/brancasheet.pdf")
    else:
        print("Arquivo brancasheet.pdf não encontrado.")