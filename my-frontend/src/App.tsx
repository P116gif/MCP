import React, {useState } from "react"
import type {FormEvent} from "react";
import api from "./api"
import type { QueryRequest, QueryResponse } from "./api";

const App: React.FC = () => {
    const [query, setQuery] = useState<string>("");
    const [response, setResponse] = useState<string>("");
    const [loading, setLoading] = useState<boolean>(false);

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setResponse("");
        try{

            const res = await api.post<QueryResponse>("/query", { query } as QueryRequest);

            setResponse(res.data.response);
        } 
        catch(error){
            setResponse("Error: " + (error as Error).message);
        }
        finally {
            setLoading(false);
        }
    };

    return (
        <div style={{maxWidth: 600, margin: "2rem auto", fontFamily: "Arial, sans-serif"}}>
            <h1>FASTAPI Query Frontend</h1>
            <form onSubmit={handleSubmit}>
                <input 
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Enter your query"
                    style={{width: "80%", padding: 8}}
                    />
                <button type="submit" style={{ marginLeft: 8}} disabled={loading}>
                    {loading ? "Sending..." : "Send"}
                </button>
            </form>
            <div style={{marginTop: "20"}}>
                <strong> Response</strong>
                <pre>{response}</pre>
                </div>
            </div>
    );
};

export default App;
// Note: The code above is a React component that uses TypeScript to create a simple frontend for sending queries to a FastAPI backend.