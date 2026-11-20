"""Tests for Paack's status e-mails in its five languages.

Paack's e-mails share one template: a header, a status, a title and a
sentence, then the shop and the order ID in a details table. A return notice
also names the failed attempt that led to it, and a pickup notice says the
order was delivered to the point, so some phrases decide wherever they
stand. The texts follow Paack's wording, with a made-up shop, point, dates
and ID.
"""

from __future__ import annotations

import pytest

from custom_components.parcels.const import CONFIDENCE_APPLY, MailKind
from custom_components.parcels.parsers.base import Eta

from .test_carriers_common import eta
from .test_carriers_es import PAACK_ID, _paack

SHOP = "Casa Exemplo"
# Paack's shop and order-number labels. Each label and its value share a row
# of the details table, so they share a line of the text.
LABELS = {
    "pt": ("Pedido de", "Número de pedido"),
    "es": ("Pedido de", "Número de pedido"),
    "fr": ("Commande auprès de", "Numéro de commande"),
    "it": ("Ordine di", "Numero d'ordine"),
    "en": ("Order from", "Order number"),
}
LANGUAGES = tuple(LABELS)
SLOT = eta("2026-11-25", "09:00", "13:00")
TODAY = eta("2026-11-17", "10:00", "12:00")
PICKUP = eta("2026-11-17", until="2026-11-24")
RESCHEDULED = {
    "pt": "Não foi possível entregar e será reagendado",
    "es": "No ha podido ser entregado y será reprogramado",
    "fr": "N'a pas pu être livrée et sera reprogrammée",
    "it": "Non è stato possibile consegnarlo e sarà riprogrammata la consegna",
    "en": "Couldn\u2019t be delivered and will be rescheduled",
}
NOT_FOUND = {
    "pt": "Não foi possível entregar o seu pedido",
    "es": "No hemos podido entregar tu pedido",
    "fr": "Nous n'avons pas été en mesure de livrer votre commande",
    "it": "Non abbiamo potuto consegnare il tuo ordine",
    "en": "We couldn't deliver your order",
}

# Each scenario: the kind, the expected date and, per language, the header,
# the status, the title and the sentence.
SCENARIOS: dict[str, tuple[MailKind, Eta | None, dict[str, tuple[str, ...]]]] = {
    "information_received": (
        MailKind.SHIPPED,
        SLOT,
        {
            "pt": (
                "Será entregue em 25/11/2026 entre as 09:00 e as 13:00",
                "Detalhes do pedido recebidos",
                "Informação recebida",
                "Recebemos os detalhes do seu pedido de Casa Exemplo. Estamos à "
                "espera que o seu volume dê entrada no nosso centro de "
                "distribuição.",
            ),
            "es": (
                "Será entregado el 25/11/2026 entre las 09:00 y las 13:00",
                "Detalles del pedido recibidos",
                "Información recibida",
                "Hemos recibido los detalles de tu pedido de Casa Exemplo. "
                "Estamos esperando que tu paquete llegue a nuestro centro de "
                "distribución.",
            ),
            "fr": (
                "Sera livré le 25/11/2026 entre 09:00 et 13:00",
                "Détails de la commande reçue",
                "Informations reçues",
                "Nous avons reçu les détails de votre commande de Casa Exemplo. "
                "Nous attendons l'arrivée de votre colis dans notre centre de "
                "distribution.",
            ),
            "it": (
                "Sarà consegnato il 25/11/2026 tra le 09:00 e le 13:00",
                "Dettagli dell'ordine ricevuto",
                "Informazioni ricevute",
                "Abbiamo ricevuto i dettagli del tuo ordine di Casa Exemplo. "
                "Stiamo aspettando che il tuo pacco arrivi al nostro centro di "
                "distribuzione.",
            ),
            "en": (
                "Will be delivered on 25/11/2026 between 09:00 and 13:00",
                "Order details received",
                "Information received",
                "We received your Casa Exemplo order details. We are waiting for "
                "your parcel to arrive at our distribution centre.",
            ),
        },
    ),
    "at_depot": (
        MailKind.IN_TRANSIT,
        SLOT,
        {
            "pt": (
                "Será entregue em 25/11/2026 entre as 09:00 e as 13:00",
                "No centro de distribuição da Paack",
                "Já o recebemos!",
                "O seu pedido a Casa Exemplo chegou ao centro de distribuição da "
                "Paack.",
            ),
            "es": (
                "Será entregado el 25/11/2026 entre las 09:00 y las 13:00",
                "En el centro de distribución de Paack",
                "¡Lo tenemos!",
                "Tu pedido de Casa Exemplo ha llegado al centro de distribución "
                "de Paack.",
            ),
            "fr": (
                "Sera livrée le 25/11/2026 entre 09:00 et 13:00",
                "Au centre de distribution de Paack",
                "Nous l'avons\u2009!",
                "Votre commande de Casa Exemplo est arrivée au centre de "
                "distribution de Paack.",
            ),
            "it": (
                "Sarà consegnato il 25/11/2026 tra le 09:00 e le 13:00",
                "Il centro di distribuzione di Paack",
                "Ci siamo!",
                "Il tuo ordine di Casa Exemplo è arrivato al centro di "
                "distribuzione di Paack.",
            ),
            "en": (
                "Will be delivered on 25/11/2026 between 09:00 and 13:00",
                "In Paack's distribution centre",
                "We\u2019ve got it!",
                "Your Casa Exemplo order has arrived at Paack's distribution centre.",
            ),
        },
    ),
    "out_for_delivery": (
        MailKind.OUT_FOR_DELIVERY,
        TODAY,
        {
            "pt": (
                "Será entregue hoje entre as 10:00 e as 12:00",
                "Em distribuição",
                "A caminho!",
                "O estafeta recolheu o seu pedido de Casa Exemplo e esta a "
                "caminho para realizar a entrega.",
            ),
            "es": (
                "Llegará hoy entre las 10:00 y las 12:00",
                "En reparto",
                "¡En camino!",
                "El repartidor ha recogido tu pedido de Casa Exemplo y está de "
                "camino para realizar la entrega.",
            ),
            "fr": (
                "Arrivera aujourd'hui entre 10:00 et 12:00",
                "En cours de livraison",
                "La commande est en chemin !",
                "Le livreur a récupéré votre commande passée chez Casa Exemplo et "
                "est en route pour effectuer la livraison.",
            ),
            "it": (
                "Arriverà oggi tra le 10:00 e le 12:00",
                "In consegna",
                "In arrivo!",
                "Il tuo ordine di Casa Exemplo è in consegna. Saremo da te al più "
                "presto.",
            ),
            "en": (
                "Will arrive today between 10:00 and 12:00",
                "Out for delivery",
                "It\u2019s on its way!",
                "The courier picked up your Casa Exemplo order and is on route to "
                "make the delivery.",
            ),
        },
    ),
    "delivered": (
        MailKind.DELIVERED,
        None,
        {
            "pt": (
                "Chegou",
                "Entregue",
                "Pedido entregue!",
                "O seu pedido a Casa Exemplo foi entregue em 17/11/2026 às 08:40.",
                "Como correu a experiência de entrega?",
            ),
            "es": (
                "Ha llegado",
                "Entregado",
                "¡Pedido entregado!",
                "Tu pedido de Casa Exemplo fue entregado el 17/11/2026 a las 08:40.",
                "¿Cómo fue tu experiencia de entrega?",
            ),
            "fr": (
                "Est arrivée",
                "Livrée",
                "Commande livrée !",
                "Votre commande de Casa Exemplo a été livrée le 17/11/2026 à 08:40.",
                "Comment s'est déroulée votre livraison\u2009?",
            ),
            "it": (
                "È arrivato",
                "Consegnato",
                "Ordine consegnato!",
                "Il tuo ordine di Casa Exemplo è stato consegnato il 17/11/2026 "
                "alle 08:40.",
                "Com'è andata la consegna?",
            ),
            "en": (
                "Has arrived",
                "Delivered",
                "Order delivered!",
                "Your Casa Exemplo order was delivered on 17/11/2026 at 08:40.",
                "How was your delivery experience?",
            ),
        },
    ),
    "collected": (
        MailKind.DELIVERED,
        None,
        {
            "pt": (
                "Coletado do PaackGo Point",
                "Entregue",
                "Você recebeu seu pedido!",
                "Seu pedido da Casa Exemplo foi coletado em PaackGo Point Exemplo "
                "no dia 17/11/2026 às 08:40.",
            ),
            "es": (
                "Recogido en PaackGo Point",
                "Entregado",
                "¡Has recibido tu pedido!",
                "Tu pedido de Casa Exemplo fue recogido en PaackGo Point Exemplo "
                "el 17/11/2026 a las 08:40.",
            ),
            "fr": (
                "Récupéré depuis un PaackGo Point",
                "Livré",
                "Vous avez reçu votre commande !",
                "Votre commande de Casa Exemplo a été récupérée chez PaackGo "
                "Point Exemplo le 17/11/2026 à 08:40.",
            ),
            "it": (
                "Ritirato dal PaackGo Point",
                "Consegnato",
                "Hai ricevuto il tuo ordine!",
                "Il tuo ordine Casa Exemplo è stato ritirato da PaackGo Point "
                "Exemplo il 17/11/2026 alle 08:40.",
            ),
            "en": (
                "Collected from PaackGo Point",
                "Delivered",
                "You've Received Your Order!",
                "Your Casa Exemplo order was collected from PaackGo Point Exemplo "
                "on 17/11/2026 at 08:40.",
            ),
        },
    ),
    "dropped_at_point": (
        MailKind.READY_FOR_PICKUP,
        PICKUP,
        {
            "pt": (
                "Pedido entregue em PaackGo Point Exemplo",
                "No PaackGo Point",
                "Seu pedido está pronto para retirada!",
                "Seu pedido Casa Exemplo foi entregue em 17/11/2026 às 08:40 e "
                "agora está disponível para retirada em PaackGo Point Exemplo, "
                "localizado em Rua Exemplo 1, 1000-001 Lisboa. Você tem até "
                "24/11/2026 para retirá-lo.",
            ),
            "es": (
                "Pedido dejado en PaackGo Point Exemplo",
                "En PaackGo Point",
                "¡Tu pedido está listo para recoger!",
                "Tu pedido de Casa Exemplo fue dejado el 17/11/2026 a las 08:40 y "
                "ahora está disponible para recoger en PaackGo Point Exemplo, "
                "ubicado en Rua Exemplo 1, 1000-001 Lisboa. Tienes hasta el "
                "24/11/2026 para recogerlo.",
            ),
            "fr": (
                "Commande déposée à PaackGo Point Exemplo",
                "Au PaackGo Point",
                "Votre commande est prête à être récupérée !",
                "Votre commande Casa Exemplo a été déposée le 17/11/2026 à 08:40 "
                "et est maintenant disponible pour être récupérée à PaackGo Point "
                "Exemplo, situé à Rua Exemplo 1, 1000-001 Lisboa. Vous avez "
                "jusqu'au 24/11/2026 pour la récupérer.",
            ),
            "it": (
                "Ordine consegnato a PaackGo Point Exemplo",
                "Presso PaackGo Point",
                "Il tuo ordine è pronto per essere ritirato!",
                "Il tuo ordine Casa Exemplo è stato consegnato il 17/11/2026 alle "
                "08:40 ed è ora disponibile per il ritiro presso PaackGo Point "
                "Exemplo, situato a Rua Exemplo 1, 1000-001 Lisboa. Hai tempo "
                "fino al 24/11/2026 per ritirarlo.",
            ),
            "en": (
                "Order dropped off at PaackGo Point Exemplo",
                "At PaackGo Point",
                "Your Order is Ready for Pickup!",
                "Your Casa Exemplo order was dropped off on 17/11/2026 at 08:40 "
                "and is now available for pickup at PaackGo Point Exemplo, "
                "located at Rua Exemplo 1, 1000-001 Lisboa. You have until the "
                "24/11/2026 to pick it up.",
            ),
        },
    ),
    "rejected": (
        MailKind.RETURN,
        None,
        {
            "pt": (
                "Foi rejeitado e será retornou",
                "Rejeitado pelo cliente",
                "Retorno em andamento",
                "Lamentamos que tenha rejeitado o seu pedido de Casa Exemplo em "
                "17/11/2026 às 08:40. Iremos devolvê-lo a Casa Exemplo.",
            ),
            "es": (
                "Ha sido rechazado y será devuelto",
                "Rechazado por el cliente",
                "Devolución en proceso",
                "Lamentamos que hayas rechazado tu pedido de Casa Exemplo el "
                "17/11/2026 a las 08:40. Procederemos a devolverlo a Casa "
                "Exemplo.",
            ),
            "fr": (
                "Votre commande a été rejetée et vous sera retournée",
                "Refusé par le client",
                "Retour en cours",
                "Nous sommes désolés d'apprendre que votre commande de Casa "
                "Exemplo a été rejetée le 17/11/2026 à 08:40. Nous allons le "
                "retourner à Casa Exemplo.",
            ),
            "it": (
                "È stato rifiutato e sarà restituito",
                "Rifiutato dal cliente",
                "Reso in corso",
                "Ci dispiace che tu abbia rifiutato il tuo ordine di Casa Exemplo "
                "il 17/11/2026 alle 08:40. Procederemo con la restituzione a Casa "
                "Exemplo.",
            ),
            "en": (
                "Was rejected and will be returned",
                "Rejected by customer",
                "Return in progress",
                "We are sorry to hear you have rejected your Casa Exemplo order "
                "on 17/11/2026 at 08:40. We will proceed to return it to Casa "
                "Exemplo.",
            ),
        },
    ),
    "return_after_attempt": (
        MailKind.RETURN,
        None,
        {
            "pt": (
                "Não foi possível entregar e será devolvido",
                "Falha na entrega",
                "Retorno em andamento",
                "Tentámos entregar o seu pedido de Casa Exemplo em 17/11/2026 às "
                "08:40, mas ocorreu um problema. Estamos a gerir a devolução do "
                "seu pedido a Casa Exemplo.",
            ),
            "es": (
                "No ha podido ser entregado y será devuelto",
                "Entrega fallida",
                "Devolución en proceso",
                "Hemos intentado entregar tu pedido de Casa Exemplo el 17/11/2026 "
                "a las 08:40 pero hubo un problema. Estamos gestionando la "
                "devolución de tu pedido a Casa Exemplo.",
            ),
            "fr": (
                "N'a pas pu être livré et sera retourné",
                "Échec de la livraison",
                "Retour en cours",
                "Nous avons essayé de livrer votre commande de Casa Exemplo le "
                "17/11/2026 à 08:40 mais il y a eu un problème. Nous nous "
                "occupons du retour de votre commande à Casa Exemplo.",
            ),
            "it": (
                "Non è stato possibile consegnarlo e sarà restituito",
                "Consegna non riuscita",
                "Reso in corso",
                "Abbiamo provato a consegnare il tuo ordine di Casa Exemplo il "
                "17/11/2026 alle 08:40 ma si è verificato un problema. Stiamo "
                "gestendo il reso del tuo ordine a Casa Exemplo.",
            ),
            "en": (
                "Couldn\u2019t be delivered and will be returned",
                "Failed delivery attempt",
                "Return in progress",
                "We tried to deliver your Casa Exemplo order on 17/11/2026 at "
                "08:40 but there was a problem. We are now managing the return of "
                "your order to Casa Exemplo.",
            ),
        },
    ),
    "returned_to_shop": (
        MailKind.RETURN,
        None,
        {
            "pt": (
                "Foi devolvido",
                "Devolução a Casa Exemplo",
                "Devolução a Casa Exemplo",
                "Seu pedido foi devolvido para Casa Exemplo em 17/11/2026 às 08:40.",
            ),
            "es": (
                "Fue devuelto",
                "Devuelto a Casa Exemplo",
                "Devuelto a Casa Exemplo",
                "Su pedido ha sido devuelto a Casa Exemplo el 17/11/2026 a las 08:40.",
            ),
            "fr": (
                "A été retourné",
                "Retournée à Casa Exemplo",
                "Retournée à Casa Exemplo",
                "Votre commande a été retourné à Casa Exemplo le 17/11/2026 à 08:40.",
            ),
            "it": (
                "È stato restituito",
                "Restituito a Casa Exemplo",
                "Restituito a Casa Exemplo",
                "Il tuo ordine è stato restituito a Casa Exemplo il 17/11/2026 "
                "alle 08:40.",
            ),
            "en": (
                "Was returned",
                "Returned to Casa Exemplo",
                "Returned to Casa Exemplo",
                "Your order has been returned to Casa Exemplo on 17/11/2026 at 08:40.",
            ),
        },
    ),
    "expired_at_point": (
        MailKind.RETURN,
        None,
        {
            "pt": (
                "Expirado e será devolvido",
                "Expirado no PaackGo Point",
                "Devolução em andamento",
                "O tempo para retirar seu pacote em PaackGo Point Exemplo "
                "expirou. Vamos proceder com a devolução para Casa Exemplo.",
            ),
            "es": (
                "Ha expirado y será devuelto",
                "Expirado en PaackGo Point",
                "Devolución en curso",
                "El tiempo para recoger tu paquete en PaackGo Point Exemplo ha "
                "expirado. Procederemos a devolverlo a Casa Exemplo.",
            ),
            "fr": (
                "Expiré et sera retourné",
                "Expiré au PaackGo Point",
                "Retour en cours",
                "Le délai pour récupérer votre colis à PaackGo Point Exemplo a "
                "expiré. Nous procéderons au retour à Casa Exemplo.",
            ),
            "it": (
                "Scaduto e verrà restituito",
                "Scaduto presso PaackGo Point",
                "Reso in corso",
                "Il tempo per ritirare il tuo pacco presso PaackGo Point Exemplo "
                "è scaduto. Procederemo con il reso a Casa Exemplo.",
            ),
            "en": (
                "Is expired and will be returned",
                "Expired at PaackGo Point",
                "Return in Progress",
                "The time to pick up your parcel at PaackGo Point Exemplo has "
                "expired. We will proceed with returning it to Casa Exemplo.",
            ),
        },
    ),
    "cancelled": (
        MailKind.CANCELLED,
        None,
        {
            "pt": (
                "Foi cancelado",
                "Cancelado",
                "Pedido cancelado",
                "Lamentamos informar que seu pedido de Casa Exemplo foi cancelado "
                "em 17/11/2026 às 08:40, portanto não será entregue.",
            ),
            "es": (
                "Ha sido cancelado",
                "Cancelado",
                "Pedido cancelado",
                "Lamentamos comunicarte que tu pedido de Casa Exemplo fue "
                "cancelado el 17/11/2026 a las 08:40, por lo que no será "
                "entregado.",
            ),
            "fr": (
                "A été annulée",
                "Annulée",
                "Commande annulée",
                "Nous avons le regret de vous informer que votre commande chez "
                "Casa Exemplo a été annulée le 17/11/2026 à 08:40, et qu\u2019elle ne "
                "sera donc pas livrée.",
            ),
            "it": (
                "È stato annullato",
                "Annullato",
                "Ordine annullato",
                "Ci dispiace comunicarti che il tuo ordine da Casa Exemplo è "
                "stato annullato il 17/11/2026 alle 08:40, quindi non sarà "
                "consegnato.",
            ),
            "en": (
                "Was cancelled",
                "Cancelled",
                "Order cancelled",
                "We are sorry to inform you that your order from Casa Exemplo was "
                "cancelled on 17/11/2026 at 08:40, so it will not be delivered.",
            ),
        },
    ),
    "customer_absent": (
        MailKind.ATTEMPTED,
        None,
        {
            "pt": (
                RESCHEDULED["pt"],
                "Cliente ausente",
                "Não o encontrámos",
                "Tentámos entregar o seu pedido de Casa Exemplo em 17/11/2026 às "
                "08:40, mas não o encontrámos. Não se preocupe que tentaremos "
                "novamente.",
            ),
            "es": (
                RESCHEDULED["es"],
                "Cliente ausente",
                "No te hemos encontrado",
                "Hemos intentado entregar tu pedido de Casa Exemplo el 17/11/2026 "
                "a las 08:40 pero no te encontramos. No te preocupes, lo "
                "intentaremos nuevamente.",
            ),
            "fr": (
                RESCHEDULED["fr"],
                "Client non trouvé",
                "Nous ne vous avons pas vu",
                "Nous avons essayé de livrer votre commande de Casa Exemplo le "
                "17/11/2026 à 08:40 mais nous ne vous avons pas vu. Ne vous "
                "inquiétez pas, nous ferons une autre tentative.",
            ),
            "it": (
                RESCHEDULED["it"],
                "Cliente assente",
                "Non ti abbiamo trovato",
                "Abbiamo provato a consegnare il tuo ordine di Casa Exemplo il "
                "17/11/2026 alle 08:40 ma non ti abbiamo trovato. Non "
                "preoccuparti, ci proveremo di nuovo.",
            ),
            "en": (
                RESCHEDULED["en"],
                "Customer absent",
                "We missed you",
                "We tried to deliver your Casa Exemplo order on 17/11/2026 at "
                "08:40 but unfortunately we missed you. Don\u2019t worry, there will "
                "be another attempt.",
            ),
        },
    ),
    "incorrect_address": (
        MailKind.ATTEMPTED,
        None,
        {
            "pt": (
                RESCHEDULED["pt"],
                "Morada incorreta",
                "Não encontramos a sua morada",
                "Tentámos entregar o seu pedido de Casa Exemplo em 17/11/2026 às "
                "08:40, mas não encontrámos a sua morada. Não se preocupe que "
                "tentaremos novamente.",
            ),
            "es": (
                RESCHEDULED["es"],
                "Dirección incorrecta",
                "No hemos encontrado tu dirección",
                "Hemos intentado entregar tu pedido de Casa Exemplo el 17/11/2026 "
                "a las 08:40 pero no hemos podido encontrar tu dirección. No te "
                "preocupes, lo intentaremos nuevamente.",
            ),
            "fr": (
                RESCHEDULED["fr"],
                "Adresse incorrecte",
                "Nous n'avons pas trouvé votre adresse",
                "Nous avons essayé de livrer votre commande de Casa Exemplo le "
                "17/11/2026 à 08:40 mais nous n'avons pas trouvé votre adresse. "
                "Ne vous inquiétez pas, nous ferons une autre tentative.",
            ),
            "it": (
                RESCHEDULED["it"],
                "Indirizzo errato",
                "Non abbiamo trovato il tuo indirizzo",
                "Abbiamo provato a consegnare il tuo ordine di Casa Exemplo il "
                "17/11/2026 alle 08:40 ma non siamo riusciti a trovare il tuo "
                "indirizzo. Non preoccuparti, ci riproveremo.",
            ),
            "en": (
                RESCHEDULED["en"],
                "Incorrect address",
                "We couldn't find your address",
                "We tried to deliver your Casa Exemplo order on 17/11/2026 at "
                "08:40 but the delivery address provided doesn\u2019t seem to be "
                "correct. Don\u2019t worry, there will be another attempt.",
            ),
        },
    ),
    "cash_on_delivery": (
        MailKind.ATTEMPTED,
        None,
        {
            "pt": (
                RESCHEDULED["pt"],
                "Falta dinheiro na entrega",
                NOT_FOUND["pt"],
                "Tentámos entregar o seu pedido de Casa Exemplo em 17/11/2026 às "
                "08:40, mas infelizmente você não conseguiu pagar o valor "
                "esperado em dinheiro na entrega. Não se preocupe que tentaremos "
                "novamente.",
            ),
            "es": (
                RESCHEDULED["es"],
                "Falta pago contra reembolso",
                NOT_FOUND["es"],
                "Hemos intentado entregar tu pedido de Casa Exemplo el 17/11/2026 "
                "a las 08:40, pero no pudiste realizar el pago contra reembolso "
                "esperado. No te preocupes, lo intentaremos nuevamente.",
            ),
            "fr": (
                RESCHEDULED["fr"],
                "Paiement manquant à la livraison",
                NOT_FOUND["fr"],
                "Nous avons essayé de livrer votre commande de Casa Exemplo le "
                "17/11/2026 à 08:40 mais vous n'avez pas pu effectuer le paiement "
                "en contre-remboursement prévu. Ne vous inquiétez pas, nous "
                "ferons une autre tentative.",
            ),
            "it": (
                RESCHEDULED["it"],
                "Manca il pagamento alla consegna",
                NOT_FOUND["it"],
                "Abbiamo provato a consegnare il tuo ordine di Casa Exemplo il "
                "17/11/2026 alle 08:40 ma non hai potuto realizzare il pagamento "
                "alla consegna atteso. Non ti preoccupare, ci riproveremo.",
            ),
            "en": (
                RESCHEDULED["en"],
                "Missing cash on delivery",
                NOT_FOUND["en"],
                "We tried to deliver your Casa Exemplo order on 17/11/2026 at "
                "08:40, but unfortunately, you were unable to pay the expected "
                "cash-on-delivery amount for it. Don\u2019t worry, there will be "
                "another attempt.",
            ),
        },
    ),
    "failed_attempt": (
        MailKind.ATTEMPTED,
        None,
        {
            "pt": (
                RESCHEDULED["pt"],
                "Falha na entrega",
                NOT_FOUND["pt"],
                "Tentámos entregar o seu pedido de Casa Exemplo em 17/11/2026 às "
                "08:40, mas ocorreu um problema. Não se preocupe que tentaremos "
                "novamente.",
            ),
            "es": (
                RESCHEDULED["es"],
                "Entrega fallida",
                NOT_FOUND["es"],
                "Hemos intentado entregar tu pedido de Casa Exemplo el 17/11/2026 "
                "a las 08:40 pero hubo un problema. No te preocupes, lo "
                "intentaremos nuevamente.",
            ),
            "fr": (
                RESCHEDULED["fr"],
                "Échec de la livraison",
                NOT_FOUND["fr"],
                "Nous avons essayé de livrer votre commande de Casa Exemplo le "
                "17/11/2026 à 08:40 mais il y a eu un problème. Ne vous "
                "inquiétez pas, nous ferons une autre tentative.",
            ),
            "it": (
                RESCHEDULED["it"],
                "Consegna non riuscita",
                NOT_FOUND["it"],
                "Abbiamo provato a consegnare il tuo ordine di Casa Exemplo il "
                "17/11/2026 alle 08:40 ma si è verificato un problema. Non ti "
                "preoccupare, ci riproveremo.",
            ),
            "en": (
                RESCHEDULED["en"],
                "Failed delivery attempt",
                NOT_FOUND["en"],
                "We tried to deliver your Casa Exemplo order on 17/11/2026 at "
                "08:40 but there was a problem. Don\u2019t worry, there will be "
                "another attempt.",
            ),
        },
    ),
    "point_closed": (
        MailKind.ATTEMPTED,
        None,
        {
            "pt": (
                "Não pôde ser entregue e será reagendado",
                "Foi reagendado",
                "Não conseguimos entregar seu pedido no PaackGo Point",
                "Tentamos entregar seu pedido Casa Exemplo em 17/11/2026 às "
                "08:40, mas houve um problema. Vamos tentar novamente nos "
                "próximos dias.",
            ),
            "es": (
                "No se pudo entregar y será reprogramado",
                "Se ha reprogramado",
                "No pudimos entregar tu pedido en el PaackGo Point",
                "Intentamos entregar tu pedido de Casa Exemplo el 17/11/2026 a "
                "las 08:40, pero hubo un problema. Lo volveremos a intentar en "
                "los próximos días.",
            ),
            "fr": (
                "Impossible de livrer et sera reprogrammé",
                "A été reprogrammé",
                "Nous n'avons pas pu livrer votre commande au PaackGo Point",
                "Nous avons tenté de livrer votre commande Casa Exemplo le "
                "17/11/2026 à 08:40, mais il y a eu un problème. Nous "
                "réessaierons dans les prochains jours.",
            ),
            "it": (
                "Impossibile consegnare e verrà riprogrammato",
                "È stato riprogrammato",
                "Non siamo riusciti a consegnare il tuo ordine al PaackGo Point",
                "Abbiamo tentato di consegnare il tuo ordine Casa Exemplo il "
                "17/11/2026 alle 08:40, ma c'è stato un problema. Ci riproveremo "
                "nei prossimi giorni.",
            ),
            "en": (
                "Couldn\u2019t be delivered and will be rescheduled",
                "Has been rescheduled",
                "We Couldn't Deliver Your Order to the PaackGo Point",
                "We tried to deliver your Casa Exemplo order on 17/11/2026 at "
                "08:40, but there was an issue. We will try again in the coming "
                "days.",
            ),
        },
    ),
}

# Paack's notices of a parcel lost at a point, or lost on the way: there's no
# status Parcels can apply, so they go to review.
LOST: dict[str, tuple[str, ...]] = {
    "pt": (
        "Houve um problema logístico e não será entregue",
        "Problema logístico",
        "Lamentamos informar que tivemos alguns problemas inesperados com seu "
        "pedido Casa Exemplo e, infelizmente, ele não está mais disponível para "
        "retirada no PaackGo Point. Entre em contato com o serviço de "
        "atendimento ao cliente da Casa Exemplo.",
        "Ocorreu um problema logístico e não será entregue",
        "Lamentamos informar que ocorreu um problema logístico com o seu pedido "
        "de Casa Exemplo e, infelizmente, este não será entregue.",
    ),
    "es": (
        "Se presentó un problema logístico y no será entregado",
        "Problema logístico",
        "Lamentamos informarte que experimentamos algunos problemas inesperados "
        "con tu pedido de Casa Exemplo, y lamentablemente ya no está disponible "
        "para recoger en el PaackGo Point. Por favor, contacta con el servicio "
        "de atención al cliente de Casa Exemplo.",
        "Ha experimentado un problema logístico y no será entregado",
        "Lamentamos comunicarte que hemos experimentado problemas inesperados "
        "con tu pedido de Casa Exemplo y desafortunadamente, ya no será "
        "entregado.",
    ),
    "fr": (
        "Problème logistique rencontré et ne sera pas livré",
        "Problème logistique",
        "Nous sommes désolés de vous informer que nous avons rencontré des "
        "problèmes inattendus avec votre commande Casa Exemplo, et "
        "malheureusement, elle n'est plus disponible pour être récupérée au "
        "PaackGo Point. Veuillez contacter le service client de Casa Exemplo.",
        "A rencontré un problème logistique et ne sera pas livré",
        "Nous avons le regret de vous informer que nous avons rencontré des "
        "problèmes inattendus avec votre commande Casa Exemplo et qu'elle ne "
        "sera malheureusement pas livrée.",
    ),
    "it": (
        "Problema logistico riscontrato e non sarà consegnato",
        "Problema logistico",
        "Siamo spiacenti di informarti che abbiamo riscontrato alcuni problemi "
        "imprevisti con il tuo ordine Casa Exemplo e, sfortunatamente, non è più "
        "disponibile per il ritiro presso il PaackGo Point. Contatta il servizio "
        "clienti di Casa Exemplo.",
        "Si è verificato un problema di logistica e non verrà consegnato",
        "Siamo spiacenti di informarti che stiamo riscontrando alcuni problemi "
        "imprevisti con il tuo ordine Casa Exemplo e sfortunatamente non sarà "
        "consegnato.",
    ),
    "en": (
        "Experienced a logistic issue and will not be delivered",
        "Logistic issue",
        "We are sorry to inform you that we experienced some unexpected issues "
        "with your Casa Exemplo order, and unfortunately, it is no longer "
        "available for pickup at the PaackGo Point. Please contact Casa Exemplo "
        "customer service.",
        "Experienced a logistic issue and will not be delivered",
        "We are sorry to let you know that we experienced some unexpected "
        "issues with your Casa Exemplo order and unfortunately, will no longer "
        "be delivered.",
    ),
}


def _mail(language: str, *lines: str, number: str = PAACK_ID) -> str:
    """Return a Paack e-mail's text: ``lines``, then the details table."""
    shop, label = LABELS[language]
    return "\n\n".join(lines) + f"\n\n{shop} {SHOP}\n\n{label} {number}\n"


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_paack_status(scenario: str, language: str) -> None:
    """Each of Paack's notices gives its status, shop and date without the AI,
    whatever the order of its lines.
    """
    kind, expected, texts = SCENARIOS[scenario]
    lines = texts[language]
    for ordered in (lines, lines[::-1]):
        result = _paack(_mail(language, *ordered))
        assert result is not None
        assert (result.kind, result.merchant) == (kind, SHOP)
        assert result.confidence >= CONFIDENCE_APPLY
        [shipment] = result.shipments
        assert (shipment.tracking_number, shipment.eta) == (PAACK_ID, expected)


@pytest.mark.parametrize("language", LANGUAGES)
def test_paack_lost_parcel_goes_to_review(language: str) -> None:
    """A parcel that's no longer available, or won't be delivered, isn't
    ready for pickup or delivered, and isn't applied without a review.
    """
    result = _paack(_mail(language, *LOST[language]))
    assert result is None or (
        result.kind not in (MailKind.READY_FOR_PICKUP, MailKind.DELIVERED)
        and result.confidence < CONFIDENCE_APPLY
    )


def test_paack_delivered_subject() -> None:
    """The subject of Paack's delivered notice, with its question, still
    says it was delivered.
    """
    result = _paack(
        _mail("pt", *SCENARIOS["delivered"][2]["pt"]),
        subject="🎉 Entregue! Como foi a sua experiência?",
    )
    assert result is not None
    assert (result.kind, result.merchant) == (MailKind.DELIVERED, SHOP)
    assert result.confidence >= CONFIDENCE_APPLY


@pytest.mark.parametrize(
    "text",
    [
        "O seu pedido a Casa Exemplo foi entregue em 17/11/2026 às 08:40.",
        "Your Casa Exemplo order was delivered on 17/11/2026 at 08:40.",
        "Le livreur a récupéré votre commande passée chez Casa Exemplo et est en "
        "route pour effectuer la livraison.",
    ],
)
def test_paack_reads_shop_in_sentence(text: str) -> None:
    """Paack's sentences name the shop in their own ways."""
    result = _paack(f"{text}\n\nNúmero de pedido: {PAACK_ID}\n")
    assert result is not None
    assert result.merchant == SHOP
