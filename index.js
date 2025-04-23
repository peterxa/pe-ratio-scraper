import yahooFinance from 'yahoo-finance2';

const data = await yahooFinance.quoteSummary("VOO", { modules: ["summaryDetail"] });
console.log(data.summaryDetail.trailingPE);
