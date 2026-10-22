export type Review = {
 id: string; ticket_id: string; enrichment_id: string; status: "pending" | "approved" | "rejected" | "attention";
 revision: number; reviewer: string | null; note: string | null; decided_at: string | null;
 created_at: string; updated_at: string; subject: string; category: string; priority: string;
 enrichment_status: string; model: string; prompt_version: string; schema_version: string;
 superseded: boolean; reviewable: boolean;
};
export type ReviewDetail = Review & {
 ticket: { id:string; subject:string; body:string; source_event_id:string; status:string; category:string; created_at:string };
 enrichment: { id:string; status:string; category:string; priority:string; reason:string; model:string; model_digest:string; prompt_version:string; schema_version:string; diagnostic_code:string; confidence:number|null };
};
export type ReviewList = {items:Review[]; total:number; limit:number; offset:number};
export type Summary = {total_tickets:number; pending:number; approved:number; rejected:number; attention:number; enrichment:Record<string,number>};
export type ReviewHistory = {items:{id:string;event:string;reviewer:string;timestamp:string;status:string;revision:number}[]};
