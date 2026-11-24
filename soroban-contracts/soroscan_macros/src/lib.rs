/*!
 * Procedural macros for standardized SoroScan event emission.
 *
 * This crate provides the `emit_soroscan_event!` macro which simplifies
 * standardized event topic and data formatting for SoroScan-indexed events.
 */

extern crate proc_macro;

use proc_macro::TokenStream;
use proc_macro2::TokenStream as TokenStream2;
use quote::quote;
use syn::parse::Parser;
use syn::punctuated::Punctuated;
use syn::{Expr, Token};

/// Split a macro input into its top-level, comma-separated arguments.
///
/// Parsing through `syn`'s expression parser (instead of splitting the
/// stringified token stream on `,`) is what keeps a compound payload such as a
/// tuple `(a, b)` together as one argument rather than truncating it at its
/// first internal comma.
fn parse_args(input: TokenStream2) -> syn::Result<Vec<Expr>> {
    let parser = Punctuated::<Expr, Token![,]>::parse_terminated;
    Ok(parser.parse2(input)?.into_iter().collect())
}

/// Emit a standardized SoroScan event with topics and payload.
///
/// This macro simplifies event emission by:
/// - Automatically formatting topics as (symbol_short!("soroscan"), event_type)
/// - Ensuring consistent XDR encoding of topics and data
/// - Reducing boilerplate for event emission
///
/// # Syntax
/// ```ignore
/// emit_soroscan_event!(env, event_type_symbol, payload_data)
/// ```
///
/// # Example
/// ```ignore
/// emit_soroscan_event!(env, symbol_short!("swap"), (
///     sender,
///     receiver,
///     amount
/// ));
/// ```
///
/// # Expands to
/// ```ignore
/// env.events().publish(
///     (symbol_short!("soroscan"), symbol_short!("swap")),
///     (sender, receiver, amount)
/// )
/// ```
#[proc_macro]
#[allow(clippy::needless_pass_by_value)]
pub fn emit_soroscan_event(input: TokenStream) -> TokenStream {
    expand_emit_soroscan_event(TokenStream2::from(input))
        .unwrap_or_else(syn::Error::into_compile_error)
        .into()
}

fn expand_emit_soroscan_event(input: TokenStream2) -> syn::Result<TokenStream2> {
    let args = parse_args(input)?;
    if args.len() != 3 {
        return Err(syn::Error::new(
            proc_macro2::Span::call_site(),
            "Expected: emit_soroscan_event!(env, event_type, payload)",
        ));
    }

    let env_expr = &args[0];
    let event_type = &args[1];
    let payload = &args[2];

    Ok(quote! {
        {
            use soroban_sdk::symbol_short;
            (#env_expr).events().publish(
                (symbol_short!("soroscan"), #event_type),
                #payload
            )
        }
    })
}

/// Emit a batch of SoroScan events with summary.
///
/// This macro simplifies batch event emission by:
/// - Automatically formatting batch topic as (symbol_short!("soroscan"), symbol_short!("batch"))
/// - Encoding batch metadata consistently
/// - Reducing boilerplate for batch operations
///
/// # Syntax
/// ```ignore
/// emit_soroscan_batch!(env, indexer, event_count, total_count)
/// ```
///
/// # Example
/// ```ignore
/// emit_soroscan_batch!(env, indexer_addr, 5, 42)
/// ```
///
/// # Expands to
/// ```ignore
/// env.events().publish(
///     (symbol_short!("soroscan"), symbol_short!("batch")),
///     (indexer_addr, 5, 42)
/// )
/// ```
#[proc_macro]
#[allow(clippy::needless_pass_by_value)]
pub fn emit_soroscan_batch(input: TokenStream) -> TokenStream {
    expand_emit_soroscan_batch(TokenStream2::from(input))
        .unwrap_or_else(syn::Error::into_compile_error)
        .into()
}

fn expand_emit_soroscan_batch(input: TokenStream2) -> syn::Result<TokenStream2> {
    let args = parse_args(input)?;
    if args.len() != 4 {
        return Err(syn::Error::new(
            proc_macro2::Span::call_site(),
            "Expected: emit_soroscan_batch!(env, indexer, event_count, total_count)",
        ));
    }

    let env_expr = &args[0];
    let indexer = &args[1];
    let event_count = &args[2];
    let total_count = &args[3];

    Ok(quote! {
        {
            use soroban_sdk::symbol_short;
            (#env_expr).events().publish(
                (symbol_short!("soroscan"), symbol_short!("batch")),
                (#indexer, #event_count, #total_count)
            )
        }
    })
}

/// Format an event topic vector with consistent naming.
///
/// This macro ensures standardized topic field naming by:
/// - Validating topic identifiers are valid symbols
/// - Converting to symbol_short! automatically
/// - Maintaining consistent formatting across events
///
/// # Syntax
/// ```ignore
/// soroscan_topics![event_name, field1, field2, ...]
/// ```
///
/// # Example
/// ```ignore
/// soroscan_topics![swap, from, to, amount]
/// ```
///
/// # Expands to topics vector
#[proc_macro]
#[allow(clippy::needless_pass_by_value)]
pub fn soroscan_topics(input: TokenStream) -> TokenStream {
    let parser = Punctuated::<Expr, Token![,]>::parse_terminated;
    let parsed = match parser.parse2(input.into()) {
        Ok(punct) => punct,
        Err(err) => {
            return syn::Error::new(err.span(), "Expected at least one topic identifier")
                .to_compile_error()
                .into();
        }
    };

    if parsed.is_empty() {
        return syn::Error::new(
            proc_macro2::Span::call_site(),
            "Expected at least one topic identifier",
        )
        .to_compile_error()
        .into();
    }

    // Every element must be a plain identifier so it can become symbol_short!(ident).
    let mut identifiers: Vec<syn::Ident> = Vec::with_capacity(parsed.len());
    for expr in &parsed {
        match expr {
            Expr::Path(path) if path.qself.is_none() && path.path.get_ident().is_some() => {
                identifiers.push(path.path.get_ident().unwrap().clone());
            }
            other => {
                return syn::Error::new_spanned(
                    other,
                    "Invalid identifier: topic names must be plain identifiers",
                )
                .to_compile_error()
                .into();
            }
        }
    }

    let expanded = quote! {
        {
            use soroban_sdk::{symbol_short, Vec};
            let mut topics = Vec::new(env);
            #(topics.push_back(symbol_short!(#identifiers));)*
            topics
        }
    };

    TokenStream::from(expanded)
}

#[cfg(test)]
mod tests {
    use super::*;
    use quote::quote;

    #[test]
    fn parses_three_plain_args() {
        let args = parse_args(quote!(env, symbol_short!("swap"), payload)).unwrap();
        assert_eq!(args.len(), 3);
    }

    #[test]
    fn keeps_tuple_payload_intact() {
        // A tuple payload contains commas; naive string-splitting would have
        // seen 5 args and failed. syn keeps it as one expression.
        let args = parse_args(quote!(env, symbol_short!("swap"), (a, b, c))).unwrap();
        assert_eq!(args.len(), 3);
        assert!(matches!(args[2], Expr::Tuple(_)));
    }

    #[test]
    fn rejects_wrong_argument_count() {
        assert!(expand_emit_soroscan_event(quote!(env, payload)).is_err());
        assert!(expand_emit_soroscan_event(quote!(env, a, b, c)).is_err());
    }

    #[test]
    fn rejects_empty_input() {
        assert!(expand_emit_soroscan_event(quote!()).is_err());
    }

    #[test]
    fn parses_four_args_for_batch() {
        let args = parse_args(quote!(env, indexer, 5, 42)).unwrap();
        assert_eq!(args.len(), 4);
    }

    #[test]
    fn test_parse_args_keeps_tuple_payload_as_one_argument() {
        let input = quote! { env, symbol_short!("swap"), (sender, receiver, amount) };
        let args = parse_args(input).expect("input should parse");

        assert_eq!(
            args.len(),
            3,
            "tuple payload must not be split on its commas"
        );
        match &args[2] {
            Expr::Tuple(tuple) => assert_eq!(tuple.elems.len(), 3),
            other => panic!("expected a tuple payload, got {}", quote!(#other)),
        }
    }

    #[test]
    fn test_emit_soroscan_event_expands_tuple_payload() {
        let input = quote! { env, symbol_short!("swap"), (sender, receiver, amount) };
        let expanded = expand_emit_soroscan_event(input).expect("tuple payload should expand");

        syn::parse2::<Expr>(expanded).expect("expansion must be valid Rust syntax");
    }

    #[test]
    fn test_emit_soroscan_event_rejects_wrong_arity() {
        let input = quote! { env, symbol_short!("swap") };
        assert!(expand_emit_soroscan_event(input).is_err());
    }

    #[test]
    fn test_emit_soroscan_batch_expands_nested_tuple_argument() {
        let input = quote! { env, (indexer, sub_indexer), 5, 42 };
        let expanded = expand_emit_soroscan_batch(input).expect("tuple argument should expand");

        syn::parse2::<Expr>(expanded).expect("expansion must be valid Rust syntax");
    }

    #[test]
    fn test_emit_soroscan_batch_rejects_wrong_arity() {
        let input = quote! { env, indexer, 5 };
        assert!(expand_emit_soroscan_batch(input).is_err());
    }
}
