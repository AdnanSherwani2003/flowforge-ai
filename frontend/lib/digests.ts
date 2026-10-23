export type Digest = {
 id:string; reporting_date:string; reporting_timezone:string; period_start:string; period_end:string;
 generated_at:string; status:"ready"; metrics_version:1; duplicate:boolean;
 metrics:{
  activity:{tickets_created:number; canonical_leads_created:number;
   lead_requests_observed:{created_records:number;event_replays:number;email_matches:number;legacy_duplicates:number};
   enrichment_results_completed:{succeeded:number;needs_review:number;unavailable:number};
   review_decisions:{approved:number;rejected:number}};
  snapshot:{pending_reviews:number;attention_reviews:number;processing_enrichments:number};
 };
};
export type DigestList = {items:Digest[];total:number;limit:number;offset:number;reporting_timezone:string;previous_completed_date:string};
