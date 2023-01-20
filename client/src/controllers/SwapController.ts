import { Controller } from '@hotwired/stimulus';
import { debounce } from '../utils/debounce';
import { domReady } from '../utils/domReady';

declare global {
  interface Window {
    headerSearch?: { targetOutput: string; url: string };
  }
}

/**
 * Support legacy window global approach until header search
 * can fully adopt data-attributes.
 *
 */
const getGlobalHeaderSearchOptions = (): {
  targetOutput?: string;
  termInput?: string;
  url?: string;
} => window.headerSearch || {};

/**
 * Allow for an element to trigger an async query that will
 * patch the results into a results DOM container. The query
 * input can be the controlled element or the containing form.
 * It supports the ability to update the URL with the query
 * when processed.
 *
 * @example
 *  <div id="results"></div>
 *  <input
 *    id="search"
 *    type="text"
 *    name="q"
 *    data-controller="w-swap"
 *    data-action="input->w-swap#searchLazy"
 *    data-w-swap-src-value="path/to/search"
 *    data-w-swap-target-value="#results"
 *  />
 */
export class SwapController extends Controller<
  HTMLFormElement | HTMLInputElement
> {
  static defaultClearParam = 'p';

  static targets = ['input'];

  static values = {
    icon: { default: '', type: String },
    loading: { default: false, type: Boolean },
    src: { default: '', type: String },
    target: { default: '#results', type: String },
    wait: { default: 200, type: Number },
  };

  declare readonly hasInputTarget: boolean;
  declare readonly hasTargetValue: boolean;
  declare readonly hasUrlValue: boolean;
  declare readonly inputTarget: HTMLInputElement;

  declare iconValue: string;
  declare loadingValue: boolean;
  declare srcValue: string;
  declare targetValue: string;
  declare waitValue: number;

  /** Allow cancelling of in flight async request if disconnected */
  abortController?: AbortController;
  /** The related icon element to attach the spinner to */
  iconElement?: SVGUseElement | null;
  /** Debounced function to search results and then replace the DOM */
  searchLazy?: { (...args: any[]): void; cancel(): void };
  /** Element that receives the fetch result HTML output */
  targetElement?: HTMLElement;

  /**
   * Ensure we have backwards compatibility with setting window.headerSearch
   * and allowing for elements without a controller attached to be set up.
   *
   * Will be removed in a future release.
   */
  static afterLoad(identifier: string) {
    domReady().then(() => {
      const { termInput, targetOutput, url } = getGlobalHeaderSearchOptions();

      const input = termInput
        ? (document.querySelector(termInput) as HTMLInputElement)
        : null;

      const form = input?.form;

      if (!form) return;

      if (!input.hasAttribute(`data-${identifier}-target`)) {
        input.setAttribute(`data-${identifier}-target`, 'input');
      }

      Object.entries({
        'data-controller': identifier,
        'data-action': [
          `change->${identifier}#searchLazy`,
          `input->${identifier}#searchLazy`,
        ].join(' '),
        [`data-${identifier}-src-value`]: url,
        [`data-${identifier}-target-value`]: targetOutput,
      }).forEach(([key, value]) => {
        if (!form.hasAttribute(key)) {
          form.setAttribute(key, value as string);
        }
      });
    });
  }

  connect() {
    const formContainer = this.hasInputTarget
      ? this.inputTarget.form
      : this.element;
    this.srcValue =
      this.srcValue || formContainer?.getAttribute('action') || '';
    this.targetElement = this.getTarget(this.targetValue);

    // set up icons
    this.iconElement = null;
    const iconContainer = (
      this.hasInputTarget ? this.inputTarget : this.element
    ).parentElement;

    this.iconElement = iconContainer?.querySelector('use') || null;
    this.iconValue = this.iconElement?.getAttribute('href') || '';

    // set up initial loading state (if set originally in the HTML)
    this.loadingValue = false;

    // set up debounced method
    this.searchLazy = debounce(this.search.bind(this), this.waitValue);
  }

  getTarget(targetValue = this.targetValue) {
    const targetElement = document.querySelector(targetValue);

    const foundTarget = targetElement && targetElement instanceof HTMLElement;
    const hasValidUrlValue = !!this.srcValue;

    const errors: string[] = [];

    if (!foundTarget) {
      errors.push(`Cannot find valid target element at "${targetValue}"`);
    }

    if (!hasValidUrlValue) {
      errors.push(`Cannot find valid src URL value`);
    }

    if (errors.length) {
      throw new Error(errors.join(', '));
    }

    return targetElement as HTMLElement;
  }

  /**
   * Toggle the visual spinner icon if available and ensure content about
   * to be replaced is flagged as busy.
   */
  loadingValueChanged(isLoading: boolean) {
    if (isLoading) {
      this.targetElement?.setAttribute('aria-busy', 'true');
      this.iconElement?.setAttribute('href', '#icon-spinner');
    } else {
      this.targetElement?.removeAttribute('aria-busy');
      this.iconElement?.setAttribute('href', this.iconValue);
    }
  }

  /**
   * Perform a search based on a single input query, and only if that query's value
   * differs from the current matching URL param. Once complete, update the URL param.
   * Additionally, clear the `'p'` pagination param in the URL if present, can be overridden
   * via action params if needed.
   */
  search(
    data?: CustomEvent<{ clear: string }> & {
      params?: { clear?: string };
    },
  ) {
    /** Params to be cleared when updating the location (e.g. ['p'] for page). */
    const clearParams = (
      data?.detail?.clear ||
      data?.params?.clear ||
      (this.constructor as typeof SwapController).defaultClearParam
    ).split(' ');

    const searchInput = this.hasInputTarget ? this.inputTarget : this.element;
    const queryParam = searchInput.name;
    const searchParams = new URLSearchParams(window.location.search);
    const currentQuery = searchParams.get(queryParam) || '';
    const newQuery = searchInput.value || '';

    // only do the query if it has changed for trimmed queries
    // for example - " " === "" and "first word " ==== "first word"
    if (currentQuery.trim() === newQuery.trim()) return;

    // Update search query param ('q') to the new value or remove if empty
    if (newQuery) {
      searchParams.set(queryParam, newQuery);
    } else {
      searchParams.delete(queryParam);
    }

    // clear any params (e.g. page/p) if needed
    clearParams.forEach((param) => {
      searchParams.delete(param);
    });

    const queryString = '?' + searchParams.toString();
    const url = this.srcValue;

    this.replace(url + queryString).then(() => {
      window.history.replaceState(null, '', queryString);
    });
  }

  /**
   * Abort any existing requests & set up new abort controller, then fetch and replace
   * the HTML target with the new results.
   * Cancel any in progress results request using the AbortController so that
   * a faster response does not replace an in flight request.
   */
  async replace(
    data:
      | string
      | (CustomEvent<{ url: string }> & { params?: { url?: string } }),
  ) {
    /** Parse a request URL from the supplied param, as a string or inside a custom event */
    const requestUrl =
      typeof data === 'string'
        ? data
        : data.detail.url || data.params?.url || '';

    if (this.abortController) this.abortController.abort();
    this.abortController = new AbortController();
    const { signal } = this.abortController;

    this.loadingValue = true;

    const beginEvent = this.dispatch('begin', {
      cancelable: true,
      detail: { requestUrl },
      // Stimulus dispatch target element type issue https://github.com/hotwired/stimulus/issues/642
      target: this.targetElement as HTMLInputElement,
    }) as CustomEvent<{ requestUrl: string }>;

    if (beginEvent.defaultPrevented) return Promise.resolve();

    return fetch(requestUrl, {
      headers: { 'x-requested-with': 'XMLHttpRequest' },
      signal,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.text();
      })
      .then((results) => {
        const targetElement = this.targetElement as HTMLElement;
        targetElement.innerHTML = results;
        this.dispatch('success', {
          cancelable: false,
          detail: { requestUrl, results },
          // Stimulus dispatch target element type issue https://github.com/hotwired/stimulus/issues/642
          target: targetElement as HTMLInputElement,
        });
        return results;
      })
      .catch((error) => {
        if (signal.aborted) return;
        this.dispatch('error', {
          cancelable: false,
          detail: { error, requestUrl },
          // Stimulus dispatch target element type issue https://github.com/hotwired/stimulus/issues/642
          target: this.targetElement as HTMLInputElement,
        });
        // eslint-disable-next-line no-console
        console.error(`Error fetching ${requestUrl}`, error);
      })
      .finally(() => {
        if (signal === this.abortController?.signal) {
          this.loadingValue = false;
        }
      });
  }

  /**
   * When disconnecting, ensure we reset any visual related state values and
   * cancel any in-flight requests.
   */
  disconnect() {
    this.loadingValue = false;
    this.searchLazy?.cancel();
  }
}
