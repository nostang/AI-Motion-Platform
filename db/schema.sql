--
-- PostgreSQL database dump
--

-- Dumped from database version 18.4 (Postgres.app)
-- Dumped by pg_dump version 18.4 (Postgres.app)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    user_id bigint NOT NULL,
    line_user_id character varying(100),
    display_name character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- Name: video_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.video_analyses (
    analysis_id bigint NOT NULL,
    user_id bigint NOT NULL,
    video_url text,
    analysis_type character varying(20) NOT NULL,
    processing_status character varying(20) NOT NULL,
    progress smallint DEFAULT 0 NOT NULL,
    current_stage character varying(50),
    overall_score numeric(6,2),
    metrics_json jsonb,
    feedback text,
    model_version character varying(100),
    rule_version character varying(100),
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT video_analyses_analysis_type_check CHECK (((analysis_type)::text = ANY ((ARRAY['footwork'::character varying, 'serve'::character varying, 'clear'::character varying])::text[]))),
    CONSTRAINT video_analyses_processing_status_check CHECK (((processing_status)::text = ANY ((ARRAY['uploaded'::character varying, 'processing'::character varying, 'completed'::character varying, 'failed'::character varying])::text[]))),
    CONSTRAINT video_analyses_progress_check CHECK (((progress >= 0) AND (progress <= 100)))
);


--
-- Name: video_analyses_analysis_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.video_analyses_analysis_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: video_analyses_analysis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.video_analyses_analysis_id_seq OWNED BY public.video_analyses.analysis_id;


--
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- Name: video_analyses analysis_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_analyses ALTER COLUMN analysis_id SET DEFAULT nextval('public.video_analyses_analysis_id_seq'::regclass);


--
-- Name: users users_line_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_line_user_id_key UNIQUE (line_user_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
--
-- Name: video_analyses video_analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_analyses
    ADD CONSTRAINT video_analyses_pkey PRIMARY KEY (analysis_id);


--
-- Name: idx_video_analyses_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_analyses_created_at ON public.video_analyses USING btree (created_at DESC);


--
-- Name: idx_video_analyses_external_id; Type: INDEX; Schema: public; Owner: -
--

--
-- Name: idx_video_analyses_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_analyses_status ON public.video_analyses USING btree (processing_status);


--
-- Name: idx_video_analyses_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_analyses_type ON public.video_analyses USING btree (analysis_type);


--
-- Name: idx_video_analyses_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_analyses_user_id ON public.video_analyses USING btree (user_id);


--
-- Name: video_analyses video_analyses_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_analyses
    ADD CONSTRAINT video_analyses_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;


-- Goo points wallet.  Available points and reserved points are kept
-- separately so an analysis can reserve its price before the long-running
-- AI job starts, then consume or release the reservation exactly once.
CREATE TABLE public.goo_wallets (
    user_id bigint PRIMARY KEY REFERENCES public.users(user_id) ON DELETE CASCADE,
    balance integer DEFAULT 0 NOT NULL CHECK (balance >= 0),
    reserved_balance integer DEFAULT 0 NOT NULL CHECK (reserved_balance >= 0),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.goo_transactions (
    transaction_id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
    amount integer NOT NULL,
    transaction_type character varying(30) NOT NULL,
    reference_type character varying(30) NOT NULL,
    reference_id character varying(100) NOT NULL,
    idempotency_key character varying(180) NOT NULL UNIQUE,
    metadata_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT goo_transactions_type_check CHECK (
        transaction_type IN ('topup', 'reward', 'analysis_debit', 'adjustment')
    )
);

CREATE TABLE public.analysis_charges (
    analysis_id bigint PRIMARY KEY REFERENCES public.video_analyses(analysis_id) ON DELETE CASCADE,
    user_id bigint NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
    analysis_type character varying(20) NOT NULL,
    charge_kind character varying(20) NOT NULL CHECK (charge_kind IN ('first_free', 'points', 'direct_purchase')),
    points integer DEFAULT 0 NOT NULL CHECK (points >= 0),
    status character varying(20) DEFAULT 'reserved' NOT NULL CHECK (status IN ('reserved', 'consumed', 'released')),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    settled_at timestamp with time zone
);

CREATE TABLE public.analysis_entitlements (
    entitlement_id bigserial PRIMARY KEY,
    payment_order_id character varying(100) NOT NULL UNIQUE,
    user_id bigint NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
    analysis_type character varying(20) NOT NULL CHECK (analysis_type IN ('footwork', 'serve', 'clear')),
    amount_twd integer NOT NULL CHECK (amount_twd > 0),
    status character varying(20) NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'reserved', 'consumed')),
    analysis_id bigint UNIQUE REFERENCES public.video_analyses(analysis_id) ON DELETE SET NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    consumed_at timestamp with time zone
);

ALTER TABLE public.analysis_charges
    ADD COLUMN entitlement_id bigint REFERENCES public.analysis_entitlements(entitlement_id) ON DELETE RESTRICT;

CREATE INDEX idx_goo_transactions_user_created
    ON public.goo_transactions (user_id, created_at DESC);
CREATE INDEX idx_analysis_charges_user_type
    ON public.analysis_charges (user_id, analysis_type);
CREATE UNIQUE INDEX uq_analysis_first_free_active
    ON public.analysis_charges (user_id, analysis_type)
    WHERE charge_kind = 'first_free' AND status IN ('reserved', 'consumed');
CREATE INDEX idx_analysis_entitlements_available
    ON public.analysis_entitlements (user_id, analysis_type, created_at)
    WHERE status = 'available';


--
-- PostgreSQL database dump complete
--
