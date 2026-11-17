import { useEffect, useState } from "react";
import { istDateTime } from "./format";
import { StateBox } from "./ui";
import { clearPhoneToken, createPhoneToken, phoneApi, PhoneApiError, readPhoneToken, savePhoneToken, type PhoneCatalog, type PhoneSubscription } from "./phoneApi";

export function AlertsView({ initialCompany }: { initialCompany?: string }) {
  const [catalog, setCatalog] = useState<PhoneCatalog | null>(null);
  const [record, setRecord] = useState<PhoneSubscription | null>(null);
  const [token, setToken] = useState<string | null>(readPhoneToken);
  const [symbols, setSymbols] = useState<string[]>(initialCompany ? [initialCompany] : []);
  const [groups, setGroups] = useState<string[]>(["results", "business"]);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [copied, setCopied] = useState("");
  const [restore, setRestore] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [reload, setReload] = useState(0);
  const [platform, setPlatform] = useState<"iphone" | "android">(() => /Android/i.test(navigator.userAgent) ? "android" : "iphone");

  function populate(value: PhoneSubscription) {
    setRecord(value);
    setSymbols(value.symbols);
    setGroups(value.groups);
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setError(""); setLoading(true);
      try {
        const data = await phoneApi.catalog();
        if (cancelled) return;
        setCatalog(data);
        if (token && data.available) {
          try {
            const value = await phoneApi.get(token);
            if (cancelled) return;
            setRecord(value); setGroups(value.groups);
            setSymbols(initialCompany && data.companies.some((c) => c.symbol === initialCompany) ? [...new Set([...value.symbols, initialCompany])] : value.symbols);
          } catch (e) {
            if (!(e instanceof PhoneApiError && e.status === 404)) throw e;
            if (!cancelled) setRecord(null);
          }
        }
      } catch (e) { if (!cancelled) setError((e as Error).message); }
      finally { if (!cancelled) setLoading(false); }
    }
    void load();
    return () => { cancelled = true; };
  }, [reload, token, initialCompany]);

  async function act(work: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await work(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  const validSymbols = symbols.filter((s) => catalog?.companies.some((c) => c.symbol === s));
  const dirty = Boolean(record && (JSON.stringify([...validSymbols].sort()) !== JSON.stringify([...record.symbols].sort()) || JSON.stringify([...groups].sort()) !== JSON.stringify([...record.groups].sort())));
  const canSave = Boolean(catalog?.available && validSymbols.length && groups.length && !busy);
  const uncheckedFollows = catalog?.last_check?.unchecked_symbols?.filter((symbol) => record?.symbols.includes(symbol)) || [];
  const delayed = catalog?.last_check ? Date.now() - Date.parse(catalog.last_check.checked_at) > 75 * 60 * 1000 : false;
  async function save(active: boolean) {
    let access = token;
    if (!access) {
      access = createPhoneToken();
      savePhoneToken(access);
      setToken(access);
    }
    const value = await phoneApi.save(access, validSymbols, groups, active);
    populate(value);
    setNotice(active ? "Your choices are saved. New matching filings will be sent to your phone." : "Your choices are saved. Connect your phone below.");
  }

  async function copy(value: string, label: string) {
    try { await navigator.clipboard.writeText(value); setCopied(label); }
    catch { setError("Select the code below and copy it using your phone's copy menu."); }
  }

  function toggle(value: string, selected: string[], setter: (values: string[]) => void) {
    setter(selected.includes(value) ? selected.filter((s) => s !== value) : [...selected, value]);
  }

  return <div className="stack phone-alerts">
    <section className="card">
      <h1>Filings for companies you follow</h1>
      <p className="muted">Choose your companies and the updates you care about. Get source-linked alerts through the free ntfy app.</p>
      <p className="fine">{catalog?.cadence || "The free service may take a minute to wake."} Up to {catalog?.max_daily || 3} alerts per day. Several filings can share one alert. Free-service limits can defer alerts.</p>
    </section>

    {loading && <StateBox kind="loading" title="Loading your alert settings…" />}
    {error && <StateBox kind="error" title="Phone alerts need attention" action={<button className="btn btn-small" onClick={() => setReload((n) => n + 1)} disabled={busy}>Reload settings</button>}>{error}</StateBox>}
    {notice && <p className="phone-feedback" role="status">{notice}</p>}
    {catalog && !loading && <>
      {!catalog.available && <StateBox kind="info" title="Phone alerts are awaiting activation">The service owner needs to connect free subscription storage and the scheduler. You can explore the company and filing choices below.</StateBox>}
      {initialCompany && !catalog.companies.some((company) => company.symbol === initialCompany) && <StateBox kind="info" title="Choose a covered company">{initialCompany} is outside FINN's current phone-alert coverage. The available companies are listed below.</StateBox>}
      <section className="card">
        <h2>Your companies</h2>
        <p className="fine">Choose from {catalog.companies.length} companies currently covered by FINN.</p>
        <label className="phone-search">Find a company<input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Company name or NSE symbol" /></label>
        <fieldset className="phone-options" disabled={busy}>
          <legend className="sr-only">Companies to follow</legend>
          {catalog.companies.filter((company) => `${company.symbol} ${company.name}`.toLowerCase().includes(search.trim().toLowerCase())).map((company) =>
            <label className="phone-choice" key={company.symbol}><input type="checkbox" checked={symbols.includes(company.symbol)} onChange={() => toggle(company.symbol, symbols, setSymbols)} />
              <span><strong>{company.symbol}</strong><span className="sub">{company.name}</span></span></label>)}
          {!catalog.companies.some((company) => `${company.symbol} ${company.name}`.toLowerCase().includes(search.trim().toLowerCase())) && <p className="muted">No covered company matches that search.</p>}
        </fieldset>
        <p className="fine" role="status">{validSymbols.length} {validSymbols.length === 1 ? "company" : "companies"} selected{validSymbols.length ? ` · ${validSymbols.join(", ")}` : ""}</p>
        <fieldset className="phone-options phone-types" disabled={busy}>
          <legend>What should reach your phone?</legend>
          {catalog.groups.map((group) => <label className="phone-choice" key={group.id}><input type="checkbox" checked={groups.includes(group.id)} onChange={() => toggle(group.id, groups, setGroups)} />
            <span><strong>{group.label}</strong><span className="sub">{group.description}</span></span></label>)}
        </fieldset>
        {dirty && <p className="fine">You have unsaved choices. Alerts use your last saved selection.</p>}
        <button className="btn btn-primary btn-block" disabled={!canSave || (Boolean(record) && !dirty)} onClick={() => void act(() => save(record?.active || false))}>{busy ? "Saving…" : record ? "Save company and filing choices" : "Set up my phone"}</button>
        {!validSymbols.length && <p className="fine">Select at least one company to continue.</p>}
        {!groups.length && <p className="fine">Select at least one filing type to continue.</p>}
      </section>

      {record && <section className="card">
        <h2>{record.active ? "Your phone is connected" : record.enabled_at ? "Your alerts are paused" : "Connect your phone"}</h2>
        <details open={!record.enabled_at}>
        <summary>{record.enabled_at ? "Connect another phone or send a test" : "Phone setup instructions"}</summary>
        <div className="phone-platform" role="group" aria-label="Your phone type">
          <button className="btn btn-small" aria-pressed={platform === "iphone"} onClick={() => setPlatform("iphone")}>iPhone</button>
          <button className="btn btn-small" aria-pressed={platform === "android"} onClick={() => setPlatform("android")}>Android</button>
        </div>
        <ol className="phone-instructions">
          <li>Install ntfy and allow notifications. <a href={platform === "iphone" ? "https://apps.apple.com/app/ntfy/id1625396347" : "https://play.google.com/store/apps/details?id=io.heckel.ntfy"} target="_blank" rel="noopener noreferrer">Get the free app ↗</a></li>
          <li>{platform === "android" ? <><a href={`ntfy://ntfy.sh/${record.topic}?display=FINN`}>Open your feed in ntfy</a>, or add a subscription manually.</> : <>In ntfy, tap <strong>+</strong> to add a subscription.</>} Use <strong>https://ntfy.sh</strong> as the server and paste this topic name.
            <div className="phone-code"><code>{record.topic}</code><button className="btn btn-small" onClick={() => void copy(record.topic, "topic")}>{copied === "topic" ? "Copied" : "Copy topic"}</button></div>
          </li>
          <li>Tap <strong>Subscribe</strong> in ntfy. Then return here and send a test.
            <button className="btn btn-block" disabled={busy || dirty} onClick={() => void act(async () => {
              const result = await phoneApi.test(token!);
              setRecord({ ...record, test_accepted_at: result.accepted_at });
              setNotice("Test accepted. Check your phone for FINN · Your phone test, then confirm below.");
            })}>{busy ? "Working…" : "Send a test to my phone"}</button>
          </li>
        </ol>
        <p className="fine">Keep the topic name private. Anyone who knows an ntfy topic can read or post to it. FINN sends public filing headlines and source links. <a href="https://docs.ntfy.sh/publish/#picking-a-topic" target="_blank" rel="noopener noreferrer">How topics work ↗</a></p>
        </details>
        {!record.active && !record.enabled_at && <button className="btn btn-primary btn-block" disabled={busy || dirty || !record.test_accepted_at} onClick={() => void act(() => save(true))}>I received the test · Enable filing alerts</button>}
        {record.active && <p className="phone-feedback">Alerts enabled for {record.symbols.join(", ")}. Newly added companies and filing types start from the time you save them.</p>}
      </section>}

      {record && <section className="card">
        <h2>Manage your alerts</h2>
        <p>{record.active ? "Receiving matching filings" : record.test_accepted_at ? "Alerts paused" : "Waiting for your phone test"}</p>
        <p className="fine">{catalog.last_check ? `Last filing check ${istDateTime(catalog.last_check.checked_at)} · ${catalog.last_check.holdings_checked}/${catalog.last_check.holdings_total} companies checked.` : "Awaiting the first scheduled filing check."}</p>
        {record.active && (delayed || uncheckedFollows.length > 0) && <StateBox kind="partial" title="Filing checks need attention">{delayed ? "The latest check is delayed. " : ""}{uncheckedFollows.length > 0 ? `Sources could not be checked for ${uncheckedFollows.join(", ")}. ` : ""}Your choices are saved. Alerts resume when source checks succeed.</StateBox>}
        {record.last_delivery_at && <p className="fine">Last alert accepted by ntfy {istDateTime(record.last_delivery_at)}.</p>}
        {record.active && <button className="btn" disabled={busy} onClick={() => void act(async () => {
          const value = await phoneApi.save(token!, record.symbols, record.groups, false);
          populate(value); setNotice("Alerts paused. Resume when you are ready.");
        })}>Pause alerts</button>}
        {!record.active && record.enabled_at && <button className="btn btn-primary" disabled={busy || dirty} onClick={() => void act(() => save(true))}>Resume alerts</button>}
        <details className="phone-access"><summary>Save my access code for another browser</summary><p className="fine">This code manages your company choices and notifications. Keep it private. Paste it into Restore my setup on another device. Clearing this browser's data removes its saved copy. Pausing or deleting here stops FINN delivery.</p>
          <div className="phone-code"><code>{token}</code><button className="btn btn-small" onClick={() => void copy(token!, "access")}>{copied === "access" ? "Copied" : "Copy access code"}</button></div>
        </details>
        {!deleteConfirm ? <button className="btn btn-small" disabled={busy} onClick={() => setDeleteConfirm(true)}>Delete my alert setup</button> : <div className="phone-delete"><p>Delete your saved companies and stop FINN delivery to this topic?</p>
          <button className="btn" disabled={busy} onClick={() => void act(async () => {
            await phoneApi.delete(token!); clearPhoneToken(); setToken(null); setRecord(null); setDeleteConfirm(false);
            setNotice("Your alert setup has been deleted. You can also remove its subscription from ntfy.");
          })}>Confirm delete</button><button className="btn" onClick={() => setDeleteConfirm(false)}>Keep my setup</button></div>}
      </section>}

      {record && record.last_items.length > 0 && <section className="card"><h2>Your last alert</h2><ul className="list">{record.last_items.map((item, index) => <li className="event" key={`${item.symbol}-${index}`}><strong>{item.title}</strong><p>{item.body.split("\n", 1)[0]}</p><p className="fine">{istDateTime(item.published_at)}</p><a className="btn btn-small" href={item.filing_url || item.company_url} target="_blank" rel="noopener noreferrer">Open source ↗</a></li>)}</ul></section>}

      <section className="card"><details><summary>Restore my setup</summary><p className="fine">Use your saved access code to manage an existing phone setup from this browser.</p><label className="phone-search">Access code<input type="password" autoComplete="off" value={restore} onChange={(e) => setRestore(e.target.value)} /></label><button className="btn" disabled={busy || !/^[A-Za-z0-9_-]{43}$/.test(restore.trim())} onClick={() => void act(async () => {
        const access = restore.trim(); const value = await phoneApi.get(access);
        savePhoneToken(access); setToken(access); populate(value); setRestore(""); setNotice("Your phone setup has been restored.");
      })}>Restore my setup</button></details></section>
    </>}
  </div>;
}
