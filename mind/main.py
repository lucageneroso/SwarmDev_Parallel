import asyncio
import os
from dotenv import load_dotenv
import parlant.sdk as p
from parlant_context.parlant_tools import (
    validate_a2a_ocl_expression, 
    publish_final_contract,
    save_design_document,
    save_roadmap_document,
    save_state_document
)

# Carichiamo automaticamente le variabili d'ambiente dal file .env
load_dotenv()

async def main():
    # Usiamo OpenRouter come provider NLP
    async with p.Server(nlp_service=p.NLPServices.openrouter) as server:
        # 1. Creazione dell'Agente SwarmDev Orchestrator
        agent = await server.create_agent(
            name="SwarmDev Orchestrator",
            description="Sei l'orchestratore del sistema multi-agente SwarmDev, responsabile dello sviluppo software parallelo basato su contratti rigorosi e validazioni A2A-OCL. Il tuo compito finale è rilasciare un Contratto JSON valido al broker messaggi."
        )
        
        # 2. Configurazione del Glossary (Vocabolario di Settore)
        await agent.create_term(
            name="A2A-OCL",
            description="Agent-to-Agent Object Constraint Language. È il linguaggio utilizzato in SwarmDev per definire i contratti e le specifiche architetturali tra agenti. Deve rispettare una precisa grammatica EBNF.",
            synonyms=["OCL", "Object Constraint Language", "Vincoli OCL"]
        )
        
        await agent.create_term(
            name="Contratto JSON",
            description="L'artefatto finale che un agente produce al termine del suo lavoro. Il contratto definisce rigidamente interfacce, modelli e vincoli A2A-OCL.",
            synonyms=["Contract", "JSON Contract", "Schema Architetturale"]
        )
        
        await agent.create_term(
            name="Micro-Loop",
            description="Il ciclo di validazione immediato dove l'agente verifica iterativamente le proprie espressioni A2A-OCL o i propri contratti JSON fino a che non risultano totalmente corretti e validi.",
            synonyms=["Micro Loop", "Self-Validation Loop", "Ciclo di Validazione"]
        )

        # 3. Configurazione delle Guidelines e del Tool
        await agent.create_guideline(
            condition="prima di inserire o confermare un'espressione A2A-OCL all'interno di un Contratto JSON",
            action="Valida sempre e rigorosamente la sintassi dell'espressione utilizzando il tool 'validate_a2a_ocl_expression' disponibile. DEVI ASSOLUTAMENTE passare l'argomento 'expression' valorizzato con la stringa OCL da testare. Correggi l'espressione iterativamente e ripeti il tool (Micro-Loop) in caso di errori fino ad ottenere 'success'!",
            tools=[validate_a2a_ocl_expression]
        )
        
        await agent.create_guideline(
            condition="L'utente ha appena proposto una nuova idea, feature o task da sviluppare in modo generico.",
            action="Fase 1 (Discovery): NON generare codice o contratti. Avvia un loop maieutico facendo domande mirate all'utente per chiarire Data Model, API, Edge Cases."
        )

        await agent.create_guideline(
            condition="Hai raccolto tutti i requisiti (Data Model, API, Edge Cases) e lo scope è chiaro.",
            action="Fase 1 (Discovery): Genera il documento di design completo in Markdown e passalo integralmente come parametro 'content' al tool save_design_document. Successivamente, chiedi esplicitamente all'utente: 'Approvi questo design?'.",
            tools=[save_design_document]
        )

        await agent.create_guideline(
            condition="L'utente ha appena approvato il DESIGN.md.",
            action="Fase 2 (Planning): Spacchetta il design in Onde logiche (Wave 1, Wave 2, ecc.). Genera la roadmap e passala come argomento 'content' al tool save_roadmap_document. Genera anche lo stato iniziale e passalo come argomento 'content' a save_state_document. Infine, chiedi all'utente l'ok per procedere alla prima Onda.",
            tools=[save_roadmap_document, save_state_document]
        )

        await agent.create_guideline(
            condition="Sei in Fase 1 o Fase 2 e l'utente NON ha ancora esplicitamente approvato il design o la roadmap.",
            action="Divieto Assoluto: È severamente vietato chiamare il tool publish_final_contract. Aspetta il consenso dell'utente."
        )

        await agent.create_guideline(
            condition="L'utente ha approvato la roadmap o ha richiesto di procedere con la prossima Onda.",
            action="Fase 3 (Execution): Per l'Onda corrente, formula tu stesso l'architettura. DEVI generare e scrivere tu le espressioni OCL, il target context e la descrizione basandoti sul documento di design. NON chiedere MAI all'utente di fornirti questi dati. Valida prima ogni espressione OCL passandola al tool validate_a2a_ocl_expression. Una volta valido, pubblica il contratto con publish_final_contract (inventando tu target_context e description). Infine salva lo stato.",
            tools=[validate_a2a_ocl_expression, publish_final_contract, save_state_document]
        )
        
        print("✅ SwarmDev Orchestrator inizializzato.")
        print("Agent, Termini Glossary e Guideline caricati con successo.")
        print("Server in esecuzione (http://localhost:8800)...")


if __name__ == "__main__":
    asyncio.run(main())
