# Matriz de regras

Fonte: `§` = seção do manual de políticas. Verificação: **T** teste, **E** eval, **D** README.
🟡 = interpretação nossa.

## Pagamento

| Código | Regra | Fonte | Ver. |
|---|---|---|---|
| PAG-01 | PIX: 5% de desconto sobre o preço de tabela | §3 | T |
| PAG-02 | PIX não desconta sobre preço promocional | §6.2 | T |
| PAG-03 | Débito e boleto à vista, sem desconto; boleto compensa em até 3 dias úteis | §3 | T |
| PAG-04 | Crédito até 12x sem juros | §3 | T |
| PAG-05 | Parcela mínima: 2–3x R$ 50; 4–6x R$ 80; 7–12x R$ 100 🟡 vale o §3.1, não a tabela do §3 | §3.1 | T |
| PAG-06 | 1x no crédito sempre permitido 🟡 | — | T |
| PAG-07 | Parcelamento máximo = maior n que respeita PAG-05 | §3.1 | T |
| PAG-08 | Combinar formas só acima de R$ 2.000 | §3.1 | T |
| PAG-09 | Parcela arredondada ao centavo 🟡 | — | T |

## Promoções

| Código | Regra | Fonte | Ver. |
|---|---|---|---|
| PRO-01 | Só vale `is_active = 1` (CSV sem datas) 🟡 | dados | T |
| PRO-02 | Mostrar preço original + % de desconto | §6.2 | T |
| PRO-03 | Promoção inativa: dizer que acabou e dar o preço atual | §7.3 | T |
| PRO-04 | Não cumulativas; duas ativas no mesmo produto → a maior 🟡 | §6.2 | T |
| PRO-05 | Sujeita a estoque, sem reserva de preço | §6.2 | E |
| PRO-06 | Calendário de campanhas é informativo, não ativa promoção | §6.1 | D |

## Catálogo

| Código | Regra | Fonte | Ver. |
|---|---|---|---|
| CAT-01 | Preço, estoque e prazo só com consulta | §7.1 | E |
| CAT-02 | Disponível = `active` e estoque > 0 | §7.3 | T |
| CAT-03 | Sem estoque: indisponível + alternativas da mesma categoria | §7.3 | T |
| CAT-04 | Descontinuado sai do catálogo mesmo com estoque (136) 🟡 | §7.3 | T |
| CAT-05 | `coming_soon` (130): "em breve", não vendável 🟡 | dados | T |
| CAT-06 | Filtro de preço usa o preço promocional, se houver 🟡 | — | T |
| CAT-07 | Ignorar descrição dos ids 135–144 (contradiz nome/specs) 🟡 | dados | T |
| CAT-08 | Categorias 6, 7, 8 vazias: "não temos no momento" | dados | T |
| CAT-09 | Busca ignora acento, caixa e aceita nome parcial | — | T |

## Frete

| Código | Regra | Fonte | Ver. |
|---|---|---|---|
| FRE-01 | Campo Grande: grátis acima de R$ 500, senão R$ 35; 1–3 dias úteis 🟡 "região metropolitana" = Campo Grande | §5.1 | T |
| FRE-02 | Valor do frete grátis conta após descontos 🟡 | §5.1 | T |
| FRE-03 | Outras cidades: PAC 5–12, SEDEX 2–5, Jadlog 3–8 dias úteis; valor por CEP, não calculado | §5.2 | T |
| FRE-04 | Fora de Campo Grande, bateria acústica, piano digital e contrabaixo acústico têm frete especial com cotação (no catálogo, só as baterias 139–141) 🟡 baixo elétrico não conta como contrabaixo | §5.2 | T |
| FRE-05 | Rastreio: `BR` + 9 alfanuméricos + `BR` (o agente só repassa o código do pedido, não valida o formato) | §5.3 | D |
| FRE-06 | Avaria na entrega: recusar o recebimento e contatar a loja | §5.2 | E |

## Pedidos

| Código | Regra | Fonte | Ver. |
|---|---|---|---|
| PED-01 | Só após verificar nº do pedido + e-mail ou telefone | §9 | T |
| PED-02 | Status: pending = aguardando pagamento, confirmed = em preparação 🟡 | dados | T |
| PED-03 | `shipped` com previsão vencida: informar atraso e encaminhar | §7.3 | T |
| PED-04 | Total informado como registrado 🟡 | dados | T |
| PED-05 | Prazos contam de `REFERENCE_DATE` (2026-03-23) 🟡 | — | T |

## Trocas, devoluções e garantia

| Código | Regra | Fonte | Ver. |
|---|---|---|---|
| DEV-01 | Arrependimento: 7 dias corridos após o recebimento, só compra online | §4.1 | T |
| DEV-02 | Recebimento = `estimated_delivery` 🟡 | — | T |
| DEV-03 | Pedido com rastreio = compra online 🟡 | — | T |
| DEV-04 | Reembolso na mesma forma em até 10 dias úteis; frete de volta pela loja | §4.1 | T |
| DEV-05 | Defeito: 30 dias corridos após a **compra**; depois, fabricante com a loja intermediando | §4.2 | T |
| DEV-09 | Mau uso, queda, umidade ou modificação não são cobertos | §4.2 | E |
| DEV-06 | Preferência: 7 dias, sujeito a disponibilidade 🟡 conta do recebimento | §4.3 | T |
| DEV-07 | Não elegíveis: personalizado, "venda final", boquilhas | §4.4 | E |
| DEV-08 | Pedido não entregue: encaminhar (manual não trata cancelamento) 🟡 | — | T |
| GAR-01 | Garantia legal: 90 dias após o recebimento | §8.1 | T |
| GAR-02 | Fabricante: 6 meses a 2 anos conforme certificado; não afirmar prazo de produto | §8.2 | E |
| GAR-03 | Não cobre desgaste, mau uso, reparo por terceiros, dano só estético | §8.3 | E |

## Loja

| Código | Regra | Fonte | Ver. |
|---|---|---|---|
| LOJ-01 | Seg–sex 9h–18h, sáb 9h–13h, dom e feriado fechado | §2 | T |
| LOJ-02 | "Aberta agora?" usa relógio real, fuso `America/Campo_Grande` | — | T |
| LOJ-03 | Feriados: só nacionais de data fixa 🟡 | §2 | T |
| LOJ-04 | Fora do expediente: informar a próxima abertura | §7.1 | T |
| LOJ-08 | Horário estendido em datas especiais não é afirmado | §2 | E |
| LOJ-05 | Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333 | §1.2 | T |
| LOJ-06 | Telefone (67) 3341-4444, WhatsApp (67) 3321-4500 🟡 §1.2 e §7 divergem | §1.2, §7 | T |
| LOJ-07 | contato@emporiodamusica.com.br 🟡 §1.2 tem erro de digitação | capa | T |

## Atendimento e escopo

| Código | Regra | Fonte | Ver. |
|---|---|---|---|
| ATD-01 | Informal mas profissional; se apresenta como assistente virtual | §7, §7.1 | E |
| ATD-02 | Saudação → entendimento → consulta → resposta → fechamento | §7.2 | E |
| ATD-03 | Reclamação: registrar e encaminhar, retorno em 24h úteis | §7.3 | T |
| ATD-04 | Dúvida na política: encaminhar, não improvisar | §10 | E |
| ATD-05 | Só instrumentos; acessórios redirecionados, sem inventar loja parceira | §7.1 | E |
| ATD-06 | Fora do escopo: recusa gentil e volta ao atendimento | enunciado | E |
| LGPD-01 | Não confirmar cadastro nem mostrar dados de outro cliente | §9 | T |
| LGPD-02 | Exclusão de dados: via WhatsApp ou e-mail | §9 | E |
| LGPD-03 | Histórico só em memória, nada vai para disco; reiniciar o processo apaga | §9 | D |

## Inconsistências dos dados

Vão para o relatório de dados; não mudam a resposta ao cliente.

| Código | Problema | Onde | Ver. |
|---|---|---|---|
| DAD-01 | Total ≠ soma dos itens | pedidos 3, 20 | T |
| DAD-02 | PIX sem os 5% no total | pedidos 1, 5, 10, 13, 17 | T |
| DAD-03 | Parcela abaixo do mínimo | pedidos 9, 16, 18 | T |
| DAD-04 | Promoção ativa não aplicada 🟡 promoção sem data, pode não valer no dia do pedido | pedidos 2, 11 | T |
| DAD-05 | `coming_soon` vendido | produto 130 (pedidos 3, 14) | T |
| DAD-06 | Descontinuado com estoque | produto 136 | T |
| DAD-07 | E-mail duplicado | clientes 11, 43 | T |
